#!/usr/bin/env python3
"""
adv_run.py -- Adversarial-training robustness experiment (T2-T7 data generation).

Reuses frozen artifacts unchanged (family folds, disassembler, features, mutation harness,
AuthGuard-M0 hyperparameters). Leakage-safe: split by frozen family BEFORE generating variants;
all variants of a source stay in the source's fold; train/test use independent RNG domains.

Outputs (raw; analysis/figures/report are separate):
  advtrain_results.json                     per model/condition/fold metrics + aggregates
  paired_results.csv                        per (sample,model,condition,fold) score+pred
  reports/advtrain_training_composition.csv
  reports/advtrain_thresholds.csv
  reports/advtrain_leakage_assertions.txt
"""
import os, sys, json, csv, time, hashlib, importlib.util, warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ag_common import normalize_bytecode, SEED
from ag_features import featurize, build_sensitive_selector_set

# reuse mutation harness unchanged
_spec = importlib.util.spec_from_file_location("mut04", os.path.join(HERE, "04_mutations.py"))
mut = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(mut)

ROOT = os.path.dirname(HERE); RES = os.path.join(ROOT, "results"); REP = os.path.join(ROOT, "reports")
SENS = build_sensitive_selector_set()
meta = json.load(open(os.path.join(RES, "feature_meta.json")))
HIST = slice(0, meta["hist_dim"])
N_SPLITS = 5

SEEN = ["M0", "M1", "M2", "F25", "F50", "F100"]
HELD = ["M3", "F200"]
ALL_TEST = ["M0", "M1", "M2", "F25", "F50", "F100", "M3", "F200"]
FRAC = {"F25": 0.25, "F50": 0.5, "F100": 1.0, "F200": 2.0}

XGB_HP = dict(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.9,
              colsample_bytree=0.8, eval_metric="logloss", random_state=SEED,
              n_jobs=4, tree_method="hist")


def make_variant(orig_hex, addr, cond, domain):
    seed_addr = f"{domain}:{addr}"
    if cond == "M0":
        return normalize_bytecode(orig_hex), "none"
    if cond in ("M1", "M2", "M3"):
        return mut.make_mutant(orig_hex, seed_addr, cond).hex(), f"{domain}:{cond}"
    frac = FRAC[cond]
    return mut.mut_deadcode_append(mut.to_bytes(orig_hex), seed_addr, frac).hex(), f"{domain}:{cond}:{frac}"


def build(sources, conditions, domain):
    """Return featurized variants for source rows across conditions. Featurize once per variant."""
    hexes, y, sid, fam, cond_l, seed_l = [], [], [], [], [], []
    for _, r in sources.iterrows():
        for c in conditions:
            h, sd = make_variant(r["bytecode"], r["sid"], c, domain)
            hexes.append(h); y.append(int(r["y"])); sid.append(r["sid"])
            fam.append(r["family_id"]); cond_l.append(c); seed_l.append(sd)
    Xd, Xn, _ = featurize(hexes, sens=SENS)
    Xfull = np.hstack([Xd, Xn]).astype(np.float32)
    return dict(Xfull=Xfull, Xhist=Xd[:, HIST].astype(np.float32),
                y=np.array(y), sid=np.array(sid), fam=np.array(fam),
                cond=np.array(cond_l), seed=np.array(seed_l),
                bchash=np.array([hashlib.sha256(h.encode()).hexdigest() for h in hexes]))


def best_f1_threshold(y, s):
    o = np.argsort(-s); ys = y[o]; tp = np.cumsum(ys); fp = np.cumsum(1 - ys); P = ys.sum()
    prec = tp / np.maximum(tp + fp, 1); rec = tp / max(P, 1)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-9)
    return float(s[o][int(np.argmax(f1))]) if len(f1) else 0.5


def metrics(y, s, thr, m0_recall=None):
    pred = (s >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    P = tp + fn; N = fp + tn
    rec = tp / P if P else float("nan"); prec = tp / (tp + fp) if (tp + fp) else 0.0
    fpr = fp / N if N else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    out = dict(AUPRC=float(average_precision_score(y, s)) if len(set(y)) > 1 else float("nan"),
               AUROC=float(roc_auc_score(y, s)) if len(set(y)) > 1 else float("nan"),
               precision=prec, recall=rec, F1=f1, FPR=fpr,
               benign_flag_rate=fpr, malicious_detected=tp, n_mal=P, n_benign=N)
    if m0_recall is not None:
        out["retained_vs_M0"] = (rec / m0_recall) if m0_recall else float("nan")
    return out


def main():
    df = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    fam = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
    df["family_id"] = fam["family_id"].values
    df = df[df["class"].isin(["malicious", "benign_cleared"])].reset_index(drop=True)
    df["y"] = (df["class"] == "malicious").astype(int)
    df["sid"] = df["chain"].astype(str) + ":" + df["address"].astype(str)  # unique source id (addr not unique across chains)

    gkf = GroupKFold(n_splits=N_SPLITS)
    folds = list(gkf.split(df, df["y"], df["family_id"]))

    models = ["opcode-histogram RF", "opcode-histogram XGBoost", "opcode-histogram XGBoost-aug",
              "AuthGuard-M0", "AuthGuard-aug"]
    results = {m: {c: [] for c in ALL_TEST} for m in models}
    paired_rows = []
    comp_rows = []
    thr_rows = []
    leak_lines = []
    scorestore = {}  # (fold,model,cond) -> dict addr->(y,score,thr,pred) for shortcut/contract analysis

    for f, (tr_idx, te_idx) in enumerate(folds):
        val_f = (f + 1) % N_SPLITS
        val_idx = folds[val_f][1]
        trainfit_idx = np.array([i for i in tr_idx if i not in set(val_idx)])
        tr = df.iloc[trainfit_idx]; va = df.iloc[val_idx]; te = df.iloc[te_idx]
        print(f"\n=== FOLD {f}: train-fit={len(tr)} val={len(va)} test={len(te)} ===", flush=True)

        # ---- leakage assertions ----
        s_tr, s_va, s_te = set(tr["sid"]), set(va["sid"]), set(te["sid"])
        f_tr, f_va, f_te = set(tr["family_id"]), set(va["family_id"]), set(te["family_id"])
        a1 = (s_tr & s_te) | (s_tr & s_va) | (s_va & s_te)
        a2 = (f_tr & f_te) | (f_tr & f_va) | (f_va & f_te)
        leak_lines.append(f"fold {f}: assert1 source-overlap(train/val/test)={len(a1)} (expect 0)")
        leak_lines.append(f"fold {f}: assert2 family-overlap(train/val/test)={len(a2)} (expect 0)")
        assert not a1 and not a2, f"fold {f} source/family leakage!"

        t0 = time.time()
        train = build(tr, SEEN, "train")
        val = build(va, ["M0"], "train")
        # per-source weight = 1/(K+1); each source has len(SEEN) instances
        cnt = pd.Series(train["sid"]).value_counts().to_dict()
        w = np.array([1.0 / cnt[a] for a in train["sid"]], dtype=np.float32)
        # composition
        for c in SEEN:
            m = train["cond"] == c
            comp_rows.append(dict(fold=f, condition=c,
                                  malicious=int(((train["y"] == 1) & m).sum()),
                                  benign=int(((train["y"] == 0) & m).sum())))
        eff_mal = float(w[train["y"] == 1].sum()); eff_ben = float(w[train["y"] == 0].sum())

        # ---- test variants (all conditions, independent seeds) ----
        test = {c: build(te, [c], "test") for c in ALL_TEST}
        # assert3/4: no mutation-instance or bytecode-hash overlap train vs test
        htr = set(train["bchash"]); hte = set(np.concatenate([test[c]["bchash"] for c in ALL_TEST]))
        leak_lines.append(f"fold {f}: assert3/4 bytecode-hash overlap(train/test)={len(htr & hte)} (expect 0)")
        assert not (htr & hte), f"fold {f} bytecode-hash leakage!"
        # assert5: every mutant inherits source family (built by construction; verify)
        inh_ok = all((test[c]["fam"] == te["family_id"].values).all() for c in ALL_TEST)
        leak_lines.append(f"fold {f}: assert5 mutant-family-inheritance ok={inh_ok}")
        assert inh_ok

        # ---- train models ----
        def fit(kind, aug):
            X = train["Xfull"] if kind == "full" else train["Xhist"]
            y = train["y"]; sw = w
            if not aug:  # M0 only, weight 1.0/source
                m0 = train["cond"] == "M0"
                X, y, sw = X[m0], y[m0], np.ones(int(m0.sum()), dtype=np.float32)
            if kind == "rf":
                clf = RandomForestClassifier(n_estimators=300, random_state=SEED, n_jobs=4)
                clf.fit(train["Xhist"][train["cond"] == "M0"], train["y"][train["cond"] == "M0"])
                return clf
            clf = XGBClassifier(**XGB_HP); clf.fit(X, y, sample_weight=sw)
            return clf

        m_rf = fit("rf", False)
        m_xgb = fit("hist", False)
        m_xgb_aug = fit("hist", True)
        m_ag = fit("full", False)
        m_ag_aug = fit("full", True)
        fitted = {"opcode-histogram RF": ("hist", m_rf),
                  "opcode-histogram XGBoost": ("hist", m_xgb),
                  "opcode-histogram XGBoost-aug": ("hist", m_xgb_aug),
                  "AuthGuard-M0": ("full", m_ag),
                  "AuthGuard-aug": ("full", m_ag_aug)}

        # ---- thresholds from clean-M0 validation ----
        thr = {}
        for name, (kind, clf) in fitted.items():
            Xv = val["Xfull"] if kind == "full" else val["Xhist"]
            sv = clf.predict_proba(Xv)[:, 1]
            thr[name] = best_f1_threshold(val["y"], sv)
            thr_rows.append(dict(fold=f, model=name, threshold=thr[name]))

        # ---- evaluate all test conditions ----
        m0_recall = {}
        for cond in ALL_TEST:
            tc = test[cond]
            for name, (kind, clf) in fitted.items():
                Xc = tc["Xfull"] if kind == "full" else tc["Xhist"]
                s = clf.predict_proba(Xc)[:, 1]
                mr = m0_recall.get(name) if cond != "M0" else None
                mm = metrics(tc["y"], s, thr[name], mr)
                if cond == "M0":
                    m0_recall[name] = mm["recall"]
                results[name][cond].append(mm)
                # paired rows
                pred = (s >= thr[name]).astype(int)
                for k in range(len(s)):
                    paired_rows.append(dict(sample_id=tc["sid"][k], family_id=tc["fam"][k],
                        fold=f, true_label=int(tc["y"][k]), model=name, condition=cond,
                        mutation_seed=tc["seed"][k], raw_score=float(s[k]),
                        threshold=thr[name], predicted_label=int(pred[k])))
        print(f"  fold {f} done in {time.time()-t0:.0f}s | "
              f"AG-M0 M3 rec={[m['recall'] for m in results['AuthGuard-M0']['M3']][-1]:.3f} "
              f"AG-aug M3 rec={[m['recall'] for m in results['AuthGuard-aug']['M3']][-1]:.3f}", flush=True)

    # ---- aggregate ----
    agg = {}
    for m in models:
        agg[m] = {}
        for c in ALL_TEST:
            dfm = pd.DataFrame(results[m][c])
            agg[m][c] = {"mean": dfm.mean(numeric_only=True).to_dict(),
                         "std": dfm.std(numeric_only=True, ddof=0).to_dict(),
                         "folds": dfm.to_dict(orient="records")}
    json.dump(dict(aggregate=agg, seen=SEEN, held_out=HELD, all_test=ALL_TEST,
                   effective_weighted_class_totals_last_fold=dict(malicious=eff_mal, benign=eff_ben)),
              open(os.path.join(ROOT, "advtrain_results.json"), "w"), indent=2)

    pd.DataFrame(paired_rows).to_csv(os.path.join(ROOT, "paired_results.csv"), index=False)
    pd.DataFrame(comp_rows).to_csv(os.path.join(REP, "advtrain_training_composition.csv"), index=False)
    pd.DataFrame(thr_rows).to_csv(os.path.join(REP, "advtrain_thresholds.csv"), index=False)
    open(os.path.join(REP, "advtrain_leakage_assertions.txt"), "w").write(
        "ALL LEAKAGE ASSERTIONS PASSED (assertions raise on failure)\n" + "\n".join(leak_lines) + "\n")

    # ---- SURFACE the gating numbers ----
    def cell(m, c, k): return agg[m][c]["mean"][k]
    print("\n" + "="*70)
    print("SURFACE (held-out gating numbers):")
    for c in ["M3", "F200"]:
        print(f"  [{c}] AuthGuard-M0 recall={cell('AuthGuard-M0',c,'recall'):.3f} "
              f"AUPRC={cell('AuthGuard-M0',c,'AUPRC'):.3f} | "
              f"AuthGuard-aug recall={cell('AuthGuard-aug',c,'recall'):.3f} "
              f"AUPRC={cell('AuthGuard-aug',c,'AUPRC'):.3f} | "
              f"benign_flag(aug)={cell('AuthGuard-aug',c,'benign_flag_rate'):.3f}")
    print(f"  [F200] opcode-XGB recall={cell('opcode-histogram XGBoost','F200','recall'):.3f} "
          f"-> XGB-aug recall={cell('opcode-histogram XGBoost-aug','F200','recall'):.3f} "
          f"benign_flag(aug)={cell('opcode-histogram XGBoost-aug','F200','benign_flag_rate'):.3f}")
    print(f"  [M0 clean] AuthGuard-M0 AUPRC={cell('AuthGuard-M0','M0','AUPRC'):.3f} "
          f"-> AuthGuard-aug AUPRC={cell('AuthGuard-aug','M0','AUPRC'):.3f} "
          f"(recall M0 {cell('AuthGuard-M0','M0','recall'):.3f}->{cell('AuthGuard-aug','M0','recall'):.3f})")
    print("="*70)


if __name__ == "__main__":
    main()
