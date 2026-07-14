#!/usr/bin/env python3
"""
ind_06_detectors.py -- T5 (exploratory) frozen-detector run + T6 false-positive controls.

Frozen models are materialized ONCE from the frozen training procedure (seed 7702) on the
USENIX training corpus (malicious 793 vs benign_cleared 1,657), thresholds fixed at max-F1 on
TRAINING data, saved+hashed BEFORE scoring any independent target. No retraining, no
threshold tuning to the independent set.

Terminology (strict): "sensitive-name rule approximation" and "external-call structural
over-approximation" -- NEVER "the USENIX detector". The full USENIX pipeline is NOT executed
here (no Gigahorse/Souffle), so NO claim is made about what it would or would not catch.

N is tiny (see funnel): results are EXPLORATORY case-study, not quantitative superiority.
"""
import os, sys, json, csv, hashlib, urllib.request, warnings, math
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ag_common import normalize_bytecode, SEED
from ag_features import featurize, build_sensitive_selector_set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results"); REP = os.path.join(ROOT, "reports")
UA = "Mozilla/5.0 (AuthGuard-7702 research; read-only; contact polboy777@gmail.com)"
EP = "https://ethereum-rpc.publicnode.com"
SENS = build_sensitive_selector_set()


def getcode(a):
    req = urllib.request.Request(EP, data=json.dumps(
        {"jsonrpc":"2.0","id":1,"method":"eth_getCode","params":[a,"latest"]}).encode(),
        headers={"Content-Type":"application/json","User-Agent":UA})
    return json.loads(urllib.request.urlopen(req, timeout=40).read())["result"]

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0, 0.0)
    p = k/n; d = 1+z*z/n
    c = (p+z*z/(2*n))/d; h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (round(p,3), round(max(0,c-h),3), round(min(1,c+h),3))

def best_f1_threshold(y, s):
    o=np.argsort(-s); ys=y[o]; tp=np.cumsum(ys); fp=np.cumsum(1-ys); P=ys.sum()
    prec=tp/np.maximum(tp+fp,1); rec=tp/max(P,1); f1=2*prec*rec/np.maximum(prec+rec,1e-9)
    return float(s[o][int(np.argmax(f1))]) if len(f1) else 0.5


def main():
    df = pd.read_csv(os.path.join(ROOT,"capability_dataset.csv"))
    Xd = np.load(os.path.join(RES,"features_dense.npz"))["X"]
    Xn = np.load(os.path.join(RES,"features_ngram.npz"))["X"]
    meta = json.load(open(os.path.join(RES,"feature_meta.json")))
    hist = slice(0, meta["hist_dim"])
    name_j = meta["dense_cols"].index("has_sensitive_selector")
    call_j = meta["dense_cols"].index("n_call_family")
    sel_cols=[i for i,c in enumerate(meta["dense_cols"]) if c.startswith("has_") or c in
              ("n_selectors","n_sensitive_selectors","n_call_family","n_delegatecall")]

    tr_mask = df["class"].isin(["malicious","benign_cleared"]).values
    ytr = (df[tr_mask]["class"]=="malicious").astype(int).values
    Xd_tr, Xn_tr = Xd[tr_mask], Xn[tr_mask]
    Xfull_tr = np.hstack([Xd_tr, Xn_tr])
    tr_mal_hashes = set(df[tr_mask][ytr.astype(bool)]["bytecode"].map(
        lambda b: hashlib.sha256(normalize_bytecode(b).encode()).hexdigest()))

    # ---- materialize + freeze models/thresholds ----
    rf=RandomForestClassifier(n_estimators=300,random_state=SEED,n_jobs=4).fit(Xd_tr[:,hist],ytr)
    xgb=XGBClassifier(n_estimators=300,max_depth=6,learning_rate=0.1,subsample=0.9,
        colsample_bytree=0.8,eval_metric="logloss",random_state=SEED,n_jobs=4,
        tree_method="hist").fit(Xd_tr[:,hist],ytr)
    ag=XGBClassifier(n_estimators=300,max_depth=6,learning_rate=0.1,subsample=0.9,
        colsample_bytree=0.8,eval_metric="logloss",random_state=SEED,n_jobs=4,
        tree_method="hist").fit(Xfull_tr,ytr)
    sc=StandardScaler().fit(Xd_tr[:,sel_cols])
    lr=LogisticRegression(max_iter=1000,random_state=SEED).fit(sc.transform(Xd_tr[:,sel_cols]),ytr)
    thr = dict(
        opcode_rf=best_f1_threshold(ytr, rf.predict_proba(Xd_tr[:,hist])[:,1]),
        opcode_xgb=best_f1_threshold(ytr, xgb.predict_proba(Xd_tr[:,hist])[:,1]),
        authguard=best_f1_threshold(ytr, ag.predict_proba(Xfull_tr)[:,1]),
        selector_lr=best_f1_threshold(ytr, lr.predict_proba(sc.transform(Xd_tr[:,sel_cols]))[:,1]))
    json.dump(thr, open(os.path.join(REP,"frozen_thresholds.json"),"w"), indent=2)

    def score_all(bcs):
        xd,xn,_=featurize(bcs,sens=SENS); xf=np.hstack([xd,xn])
        return dict(
            blocklist=np.array([hashlib.sha256(normalize_bytecode(b).encode()).hexdigest()
                                in tr_mal_hashes for b in bcs],dtype=float),
            sensitive_name_rule_approx=(xd[:,name_j]>0).astype(float),
            external_call_structural_overapprox=(xd[:,call_j]>0).astype(float),
            selector_lr=(lr.predict_proba(sc.transform(xd[:,sel_cols]))[:,1]>=thr["selector_lr"]).astype(float),
            opcode_rf=(rf.predict_proba(xd[:,hist])[:,1]>=thr["opcode_rf"]).astype(float),
            opcode_xgb=(xgb.predict_proba(xd[:,hist])[:,1]>=thr["opcode_xgb"]).astype(float),
            authguard=(ag.predict_proba(xf)[:,1]>=thr["authguard"]).astype(float))

    # ---- fetch + score the 9 independent targets ----
    tgts=list(csv.DictReader(open(os.path.join(REP,"independent_targets.csv"))))
    for t in tgts: t["bc"]=normalize_bytecode(getcode(t["target"]))
    bcs=[t["bc"] for t in tgts]
    sc_t=score_all(bcs)
    methods=list(sc_t.keys())
    # attach maliciousness/novelty from funnel classification
    mj=json.load(open(os.path.join(REP,"funnel.json")))
    malmap={r["target"]:(r["maliciousness_confidence"],r["novelty_subset"])
            for r in csv.DictReader(open(os.path.join(ROOT,"independent_malicious.csv")))}
    unc={r["target"]:(r["maliciousness_confidence"],r["novelty_subset"])
         for r in csv.DictReader(open(os.path.join(ROOT,"uncertain_candidates.csv")))}
    allmap={**malmap,**unc}

    per=[]
    for i,t in enumerate(tgts):
        conf,subset=allmap.get(t["target"],("?","?"))
        row=dict(target=t["target"], maliciousness=conf, novelty=subset,
                 **{m:int(sc_t[m][i]) for m in methods})
        per.append(row)
    with open(os.path.join(REP,"independent_detection_per_contract.csv"),"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["target","maliciousness","novelty"]+methods);w.writeheader()
        for r in per: w.writerow(r)

    # detection rate on confirmed-malicious subsets (case study, Wilson CI)
    def subset_idx(pred):
        return [i for i,t in enumerate(tgts) if pred(allmap.get(t["target"],("?","?")))]
    subsets={
        "confirmed_malicious_all": subset_idx(lambda x: x[0] in ("malicious_high","malicious_medium")),
        "confirmed_malicious_truly_novel": subset_idx(lambda x: x[0] in ("malicious_high","malicious_medium") and x[1]=="truly_novel"),
        "confirmed_malicious_known_family_or_exact": subset_idx(lambda x: x[0] in ("malicious_high","malicious_medium") and x[1] in ("known_family","exact_known")),
    }
    det={}
    for sname,idx in subsets.items():
        det[sname]={"n":len(idx)}
        for m in methods:
            k=int(sum(sc_t[m][i] for i in idx))
            det[sname][m]={"detected":k,"rate_wilson":wilson(k,len(idx))}

    # ---- T6 false-positive controls on benign sets ----
    fp={}
    for cls in ["benign_AA","benign_general","benign_cleared"]:
        m=(df["class"]==cls).values
        xd_c=Xd[m]; xf_c=np.hstack([Xd[m],Xn[m]])
        preds=dict(
            sensitive_name_rule_approx=(xd_c[:,name_j]>0).astype(float),
            external_call_structural_overapprox=(xd_c[:,call_j]>0).astype(float),
            selector_lr=(lr.predict_proba(sc.transform(xd_c[:,sel_cols]))[:,1]>=thr["selector_lr"]).astype(float),
            opcode_rf=(rf.predict_proba(xd_c[:,hist])[:,1]>=thr["opcode_rf"]).astype(float),
            opcode_xgb=(xgb.predict_proba(xd_c[:,hist])[:,1]>=thr["opcode_xgb"]).astype(float),
            authguard=(ag.predict_proba(xf_c)[:,1]>=thr["authguard"]).astype(float))
        n=int(m.sum())
        fp[cls]={"n":n,"in_training":cls=="benign_cleared",
                 **{k:{"flagged":int(v.sum()),"rate_wilson":wilson(int(v.sum()),n)} for k,v in preds.items()}}

    json.dump(dict(frozen_thresholds=thr, detection_on_independent=det,
                   false_positive_controls=fp, methods=methods,
                   note="EXPLORATORY: truly-novel confirmed N=1; no quantitative superiority claim. "
                        "Full USENIX pipeline NOT executed; no claim about it."),
              open(os.path.join(REP,"independent_detection.json"),"w"), indent=2)

    print("=== FROZEN THRESHOLDS ==="); print(json.dumps(thr,indent=1))
    print("\n=== DETECTION ON INDEPENDENT CONFIRMED-MALICIOUS (exploratory) ===")
    for s,d in det.items():
        print(f"\n[{s}] n={d['n']}")
        for m in methods: print(f"   {m:36s} {d[m]['detected']}/{d['n']}  {d[m]['rate_wilson']}")
    print("\n=== FALSE-POSITIVE CONTROLS (flag rate on benign) ===")
    for cls,d in fp.items():
        print(f"\n[{cls}] n={d['n']} in_training={d['in_training']}")
        for m in methods:
            if m in d: print(f"   {m:36s} {d[m]['flagged']}/{d['n']}  {d[m]['rate_wilson']}")
    print("\n=== PER-CONTRACT ===");
    for r in per: print("  ",r["target"],r["maliciousness"],r["novelty"],
                        "AG=",r["authguard"],"name=",r["sensitive_name_rule_approx"],
                        "struct=",r["external_call_structural_overapprox"],"xgb=",r["opcode_xgb"])


if __name__=="__main__":
    main()
