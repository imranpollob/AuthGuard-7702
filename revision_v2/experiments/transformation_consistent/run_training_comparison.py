#!/usr/bin/env python3
"""Matched-FPR comparison of clean, augmented, source-balanced, and TC-hard training."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from xgboost import XGBClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "donor_pools"))
from harness import (load_corpus, task_arrays, featurize, SENS, XGB_HP, SEED, RV2, DH,
                     verify_frozen_or_die, write_manifest)  # noqa: E402
from pools import DonorPools, make_variant_isolated  # noqa: E402

OUT = os.path.join(RV2, "results", "transformation_consistent")
MODELS = ["clean", "ordinary_aug", "source_balanced_aug", "tc_hard"]
SEEDS = [SEED, 7703, 7704]
SEEN = ["M0", "M1", "M2", "F25", "F50", "F100"]
HARD_BANK = ["M0", "M1", "M2", "M3", "F25", "F50", "F100", "F200", "M3F200"]
TEST_CONDITIONS = ["cleanM0", "F200", "M3F200", "adaptive_transfer"]
FPR_TARGETS = [0.01, 0.05, 0.10]
NBOOT = 10_000

CP_STATE = os.path.join(OUT, "checkpoint_state.json")
CP_METRICS = os.path.join(OUT, "checkpoint_metrics.csv")
CP_ROWS = os.path.join(OUT, "checkpoint_per_row.csv.gz")
CP_THRESH = os.path.join(OUT, "checkpoint_thresholds.csv")
CP_BENIGN = os.path.join(OUT, "checkpoint_benign.csv")
CP_HARD = os.path.join(OUT, "checkpoint_hard_selection.csv.gz")
CP_COMP = os.path.join(OUT, "checkpoint_training_composition.csv")
CP_DONORS = os.path.join(OUT, "checkpoint_donors.csv.gz")


def matrix(hexes):
    dense, ngram, _ = featurize(hexes, sens=SENS)
    return np.hstack([dense, ngram]).astype(np.float32)


def fit_xgb(X, y, seed, weights=None):
    model = XGBClassifier(random_state=seed, **XGB_HP)
    model.fit(X, y, sample_weight=weights)
    return model


def threshold_at_fpr(negative_scores, target):
    """Highest-coverage threshold whose empirical negative FPR does not exceed target."""
    scores = np.sort(np.asarray(negative_scores, dtype=float))[::-1]
    allowed = int(np.floor(target * len(scores) + 1e-12))
    if not len(scores):
        raise ValueError("no validation negatives")
    if allowed <= 0:
        threshold = float(np.nextafter(scores[0], np.inf))
    elif allowed >= len(scores):
        threshold = float(np.nextafter(scores[-1], -np.inf))
    else:
        upper, lower = scores[allowed - 1], scores[allowed]
        threshold = float((upper + lower) / 2.0 if upper > lower
                          else np.nextafter(upper, np.inf))
    achieved = float((scores >= threshold).mean())
    assert achieved <= target + 1e-12
    return threshold, achieved


def build_bank(pools, sources, conditions, fold, partition, domain):
    hexes, labels, sids, families, condition_rows = [], [], [], [], []
    for _, source in sources.iterrows():
        for condition in conditions:
            candidate = make_variant_isolated(pools, source.to_dict(), fold, partition,
                                               condition, domain)
            hexes.append(candidate); labels.append(int(source["y"])); sids.append(source["sid"])
            families.append(source["family_id"]); condition_rows.append(condition)
    return dict(X=matrix(hexes), y=np.asarray(labels), sid=np.asarray(sids),
                family=np.asarray(families), condition=np.asarray(condition_rows))


def source_weights(sids):
    counts = pd.Series(sids).value_counts().to_dict()
    return np.asarray([1.0 / counts[sid] for sid in sids], dtype=np.float32)


def condition_metrics(y, scores, thresholds):
    output = dict(AUPRC=float(average_precision_score(y, scores)))
    for target, threshold in thresholds.items():
        pred = scores >= threshold
        positive = y == 1; negative = y == 0
        suffix = f"{int(round(target * 100)):02d}"
        output[f"Recall_{suffix}"] = float(pred[positive].mean())
        output[f"FPR_{suffix}"] = float(pred[negative].mean())
    return output


def _atomic_csv(frame, path, compression=None):
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, compression=compression)
    os.replace(temporary, path)


def save_checkpoint(completed, metrics, rows, thresholds, benign, hard, composition,
                    donors, leakage):
    _atomic_csv(pd.DataFrame(metrics), CP_METRICS)
    _atomic_csv(pd.DataFrame(rows), CP_ROWS, "gzip")
    _atomic_csv(pd.DataFrame(thresholds), CP_THRESH)
    _atomic_csv(pd.DataFrame(benign), CP_BENIGN)
    _atomic_csv(pd.DataFrame(hard), CP_HARD, "gzip")
    _atomic_csv(pd.DataFrame(composition), CP_COMP)
    _atomic_csv(pd.DataFrame(donors), CP_DONORS, "gzip")
    temporary = CP_STATE + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(dict(completed_folds=sorted(completed), leakage=leakage,
                       counts=dict(metrics=len(metrics), rows=len(rows), thresholds=len(thresholds),
                                   benign=len(benign), hard=len(hard),
                                   composition=len(composition), donors=len(donors))),
                  handle, indent=2)
    os.replace(temporary, CP_STATE)


def load_checkpoint():
    if not os.path.exists(CP_STATE):
        return set(), [], [], [], [], [], [], [], []
    state = json.load(open(CP_STATE))
    def records(path):
        return pd.read_csv(path).to_dict(orient="records")
    data = [records(path) for path in
            [CP_METRICS, CP_ROWS, CP_THRESH, CP_BENIGN, CP_HARD, CP_COMP, CP_DONORS]]
    names = ["metrics", "rows", "thresholds", "benign", "hard", "composition", "donors"]
    assert all(len(values) == state["counts"][name] for name, values in zip(names, data))
    return (set(map(int, state["completed_folds"])), *data, list(state["leakage"]))


def summarize(records, keys, value_columns):
    frame = pd.DataFrame(records)
    output = {}
    for group_key, group in frame.groupby(keys):
        cursor = output
        values = group_key if isinstance(group_key, tuple) else (group_key,)
        for value in values[:-1]:
            cursor = cursor.setdefault(str(value), {})
        cursor[str(values[-1])] = {
            "mean": {column: float(group[column].mean()) for column in value_columns},
            "std": {column: float(group[column].std(ddof=0)) for column in value_columns},
            "folds": group.to_dict(orient="records")}
    return output


def paired_bootstrap(per_row, model_a, model_b, condition):
    frame = per_row[(per_row["seed"] == SEED) & (per_row["condition"] == condition)]
    a = frame[frame["model"] == model_a].set_index("sid").sort_index()
    b = frame[frame["model"] == model_b].set_index("sid").loc[a.index]
    assert (a["y"].to_numpy() == b["y"].to_numpy()).all()
    families = a["family_id"].to_numpy(); y = a["y"].to_numpy()
    unique = np.asarray(sorted(pd.unique(families)))
    index = {family: i for i, family in enumerate(unique)}
    row_family = np.asarray([index[family] for family in families])
    rng_seed = int.from_bytes(hashlib.blake2b(
        f"{SEED}:tc:{model_a}:{model_b}:{condition}".encode(), digest_size=8).digest(), "little")
    rng = np.random.default_rng(rng_seed)
    metrics = {"AUPRC": np.empty(NBOOT),
               **{f"Recall_{int(target*100):02d}": np.empty(NBOOT) for target in FPR_TARGETS}}
    score_a=a["score"].to_numpy(); score_b=b["score"].to_numpy(); positive=y==1
    for replicate in range(NBOOT):
        weights = np.bincount(rng.integers(0, len(unique), len(unique)),
                              minlength=len(unique))[row_family]
        metrics["AUPRC"][replicate] = (
            average_precision_score(y, score_a, sample_weight=weights) -
            average_precision_score(y, score_b, sample_weight=weights))
        for target in FPR_TARGETS:
            suffix=f"{int(target*100):02d}"
            pred_a=a[f"pred_{suffix}"].to_numpy(dtype=float)
            pred_b=b[f"pred_{suffix}"].to_numpy(dtype=float)
            denominator=(weights*positive).sum()
            metrics[f"Recall_{suffix}"][replicate] = (
                (weights*positive*(pred_a-pred_b)).sum()/denominator if denominator else np.nan)
    output={}
    for name, values in metrics.items():
        finite=values[np.isfinite(values)]
        ci=[float(np.percentile(finite,2.5)),float(np.percentile(finite,97.5))]
        if name=="AUPRC":
            point=float(average_precision_score(y,score_a)-average_precision_score(y,score_b))
        else:
            suffix=name.split("_")[1]
            point=float((a[f"pred_{suffix}"][positive].mean()-
                         b[f"pred_{suffix}"][positive].mean()))
        output[name]=dict(point=point,CI95=ci,excludes_zero=bool(ci[0]>0 or ci[1]<0),
                          boot_mean=float(finite.mean()),boot_std=float(finite.std()),
                          replicates=int(len(finite)))
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--validate-only",action="store_true")
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    started=time.time(); verify_frozen_or_die(); os.makedirs(OUT,exist_ok=True)
    df,Xd,Xn,_=load_corpus()
    sub,y,folds,Xds,Xns=task_arrays(df,Xd,Xn,"primary")
    sub=sub.copy();sub["y"]=y
    X=np.hstack([Xds,Xns]).astype(np.float32)
    bg_mask=(df["class"]=="benign_general").to_numpy()
    Xbg=np.hstack([Xd[bg_mask],Xn[bg_mask]]).astype(np.float32)
    bg=df.loc[bg_mask].reset_index(drop=True)
    attack_path=os.path.join(RV2,"results","adaptive_attacks","attack_per_row.csv.gz")
    attack=pd.read_csv(attack_path)
    adaptive=(attack[attack["method"]=="random_search"].set_index("sid")["candidate_hex"].to_dict())
    assert set(sub[sub["y"]==1]["sid"])<=set(adaptive)
    pools=DonorPools(df.assign(y=(df["class"]=="malicious").astype(int)),
                     "benign_general","outer_fold_primary","TC_HARD")

    if args.validate_only:
        for target in FPR_TARGETS:
            threshold,achieved=threshold_at_fpr(np.linspace(0,1,101),target)
            assert achieved<=target
        sample=sub.iloc[:12]
        bank=build_bank(pools,sample,HARD_BANK,int(sample.iloc[0]["outer_fold_primary"]),
                        "test","tc_validate")
        assert bank["X"].shape==(len(sample)*len(HARD_BANK),773)
        print("[validate] bank",bank["X"].shape,"targets",FPR_TARGETS)
        verify_frozen_or_die();return

    if args.resume:
        (completed,metric_rows,per_rows,threshold_rows,benign_rows,hard_rows,composition_rows,
         donors,leakage)=load_checkpoint();pools.ledger_rows=donors
        if completed: print(f"[resume] completed folds {sorted(completed)}",flush=True)
    else:
        completed=set();metric_rows=[];per_rows=[];threshold_rows=[];benign_rows=[]
        hard_rows=[];composition_rows=[];leakage=[]

    for fold in range(5):
        if fold in completed:
            print(f"[resume] skip fold {fold}",flush=True);continue
        pools.assert_disjoint(fold)
        validation_fold=(fold+1)%5
        train_idx=np.flatnonzero((folds!=fold)&(folds!=validation_fold))
        val_idx=np.flatnonzero(folds==validation_fold)
        test_idx=np.flatnonzero(folds==fold)
        train_sources=sub.iloc[train_idx]
        bank=build_bank(pools,train_sources,HARD_BANK,fold,"train","tc_train")
        condition=bank["condition"]
        m0=condition=="M0"
        seen=np.isin(condition,SEEN)
        ordinary=m0|((bank["y"]==1)&seen)
        source_w=source_weights(bank["sid"][seen])

        # Test representations are fixed once per fold for every regime/seed.
        test_sources=sub.iloc[test_idx]
        test_hex={
            "cleanM0":test_sources["bytecode"].tolist(),
            "F200":[make_variant_isolated(pools,r.to_dict(),fold,"test","F200","tc_test")
                    for _,r in test_sources.iterrows()],
            "M3F200":[make_variant_isolated(pools,r.to_dict(),fold,"test","M3F200","tc_test")
                      for _,r in test_sources.iterrows()],
            "adaptive_transfer":[adaptive[r["sid"]] if int(r["y"])==1 else r["bytecode"]
                                 for _,r in test_sources.iterrows()]}
        test_X={name:matrix(values) for name,values in test_hex.items()}

        for seed in SEEDS:
            clean_model=fit_xgb(bank["X"][m0],bank["y"][m0],seed)
            ordinary_model=fit_xgb(bank["X"][ordinary],bank["y"][ordinary],seed)
            source_model=fit_xgb(bank["X"][seen],bank["y"][seen],seed,source_w)
            bank_scores=clean_model.predict_proba(bank["X"])[:,1]
            selected=[]
            for sid,indices in pd.Series(np.arange(len(bank["sid"]))).groupby(bank["sid"]):
                idx=indices.to_numpy();label=int(bank["y"][idx[0]])
                worst=idx[np.argmin(bank_scores[idx]) if label==1 else np.argmax(bank_scores[idx])]
                base=idx[np.flatnonzero(bank["condition"][idx]=="M0")[0]]
                chosen=sorted(set([int(base),int(worst)]));selected.extend(chosen)
                hard_rows.append(dict(fold=fold,seed=seed,sid=sid,y=label,
                                      selected_condition=str(bank["condition"][worst]),
                                      clean_stage_score=float(bank_scores[worst])))
            selected=np.asarray(selected,dtype=int)
            tc_model=fit_xgb(bank["X"][selected],bank["y"][selected],seed,
                             source_weights(bank["sid"][selected]))
            fitted={"clean":clean_model,"ordinary_aug":ordinary_model,
                    "source_balanced_aug":source_model,"tc_hard":tc_model}
            composition_rows += [
                dict(fold=fold,seed=seed,model="clean",rows=int(m0.sum()),
                     total_weight=float(m0.sum())),
                dict(fold=fold,seed=seed,model="ordinary_aug",rows=int(ordinary.sum()),
                     total_weight=float(ordinary.sum())),
                dict(fold=fold,seed=seed,model="source_balanced_aug",rows=int(seen.sum()),
                     total_weight=float(source_w.sum())),
                dict(fold=fold,seed=seed,model="tc_hard",rows=int(len(selected)),
                     total_weight=float(source_weights(bank["sid"][selected]).sum()))]

            for model_name,model in fitted.items():
                val_scores=model.predict_proba(X[val_idx])[:,1]
                val_negative=val_scores[y[val_idx]==0]
                thresholds={}
                for target in FPR_TARGETS:
                    threshold,achieved=threshold_at_fpr(val_negative,target)
                    thresholds[target]=threshold
                    threshold_rows.append(dict(fold=fold,seed=seed,model=model_name,
                                               target_FPR=target,threshold=threshold,
                                               validation_achieved_FPR=achieved,
                                               validation_rows=len(val_idx),
                                               validation_negatives=len(val_negative)))
                bg_scores=model.predict_proba(Xbg)[:,1]
                for target,threshold in thresholds.items():
                    benign_rows.append(dict(fold=fold,seed=seed,model=model_name,
                                            target_FPR=target,
                                            benign_general_FPR=float((bg_scores>=threshold).mean()),
                                            n=len(bg)))
                for test_condition,test_matrix in test_X.items():
                    scores=model.predict_proba(test_matrix)[:,1]
                    metrics=condition_metrics(y[test_idx],scores,thresholds)
                    metric_rows.append(dict(fold=fold,seed=seed,model=model_name,
                                            condition=test_condition,**metrics))
                    for position,row_index in enumerate(test_idx):
                        record=dict(sid=sub["sid"].iloc[row_index],
                                    family_id=sub["family_id"].iloc[row_index],
                                    y=int(y[row_index]),fold=fold,seed=seed,
                                    model=model_name,condition=test_condition,
                                    score=float(scores[position]))
                        for target,threshold in thresholds.items():
                            suffix=f"{int(target*100):02d}"
                            record[f"threshold_{suffix}"]=threshold
                            record[f"pred_{suffix}"]=int(scores[position]>=threshold)
                        per_rows.append(record)
            print(f"[tc fold {fold}] seed {seed} complete",flush=True)
        leakage.append(f"fold {fold}: train/val/test source+family disjoint; donor pools disjoint")
        completed.add(fold)
        save_checkpoint(completed,metric_rows,per_rows,threshold_rows,benign_rows,hard_rows,
                        composition_rows,pools.ledger_rows,leakage)
        print(f"[tc checkpoint] fold {fold}",flush=True)

    metrics_frame=pd.DataFrame(metric_rows);per_frame=pd.DataFrame(per_rows)
    primary=metrics_frame[metrics_frame.seed==SEED]
    aggregate=summarize(primary,["model","condition"],
                        ["AUPRC","Recall_01","FPR_01","Recall_05","FPR_05",
                         "Recall_10","FPR_10"])
    seedwise=summarize(metric_rows,["seed","model","condition"],
                       ["AUPRC","Recall_01","FPR_01","Recall_05","FPR_05",
                        "Recall_10","FPR_10"])
    benign_summary=summarize(benign_rows,["model","target_FPR"],["benign_general_FPR"])
    uncertainty={}
    for comparator in ["clean","source_balanced_aug"]:
        uncertainty[f"tc_hard_minus_{comparator}"]={
            condition:paired_bootstrap(per_frame,"tc_hard",comparator,condition)
            for condition in TEST_CONDITIONS}

    paths={
        "metrics":os.path.join(OUT,"metrics_by_fold.csv"),
        "per_row":os.path.join(OUT,"per_row_scores.csv.gz"),
        "thresholds":os.path.join(OUT,"thresholds.csv"),
        "benign":os.path.join(OUT,"benign_general.csv"),
        "hard":os.path.join(OUT,"hard_selection.csv.gz"),
        "composition":os.path.join(OUT,"training_composition.csv"),
        "donors":os.path.join(OUT,"donor_ledger.csv.gz")}
    metrics_frame.to_csv(paths["metrics"],index=False);per_frame.to_csv(paths["per_row"],index=False)
    pd.DataFrame(threshold_rows).to_csv(paths["thresholds"],index=False)
    pd.DataFrame(benign_rows).to_csv(paths["benign"],index=False)
    pd.DataFrame(hard_rows).to_csv(paths["hard"],index=False)
    pd.DataFrame(composition_rows).to_csv(paths["composition"],index=False)
    donor_frame=pools.write_ledger(paths["donors"])
    results_path=os.path.join(OUT,"training_results.json")
    with open(results_path,"w") as handle:
        json.dump(dict(protocol="transformation_consistent_training_protocol.md",
                       models=MODELS,seeds=SEEDS,conditions=TEST_CONDITIONS,
                       FPR_targets=FPR_TARGETS,primary_seed=SEED,aggregate=aggregate,
                       seedwise=seedwise,benign_general=benign_summary,
                       family_clustered_uncertainty=uncertainty,
                       donor_ledger_rows=len(donor_frame)),handle,indent=2)
    outputs=[results_path,*paths.values()]
    write_manifest(OUT,dict(protocol="transformation_consistent_training_protocol",seeds=SEEDS,
                            models=MODELS,conditions=TEST_CONDITIONS,FPR_targets=FPR_TARGETS),
                   outputs,started,inputs=[os.path.join(DH,"task_aligned_dataset_v1.csv"),attack_path])
    verify_frozen_or_die()
    print(json.dumps(aggregate,indent=2));print(f"[tc-training] done in {time.time()-started:.0f}s")


if __name__=="__main__":
    main()
