#!/usr/bin/env python3
"""adv_analysis.py -- T6 shortcut, T7 contract-level deltas, T8 paired stats from paired_results.csv."""
import os, sys, json, math
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(ROOT, "reports")
P = pd.read_csv(os.path.join(ROOT, "paired_results.csv"))
fam = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
famsize_mal = fam[fam["class"]=="malicious"].groupby("family_id").size()
SINGLETON = set(famsize_mal[famsize_mal==1].index)
rng = np.random.default_rng(7702)


def wilson(k, n, z=1.96):
    if n==0: return (float("nan"),)*3
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (round(p,3), round(max(0,c-h),3), round(min(1,c+h),3))

def sub(model, cond):
    return P[(P.model==model)&(P.condition==cond)]

# ---------------- T6: shortcut / integrity ----------------
def t6():
    out={}
    for model in ["AuthGuard-M0","AuthGuard-aug","opcode-histogram XGBoost-aug"]:
        out[model]={}
        for c in ["M0","F25","F50","F100","F200"]:
            d=sub(model,c)
            mal=d[d.true_label==1]; ben=d[d.true_label==0]
            k_m=int(mal.predicted_label.sum()); k_b=int(ben.predicted_label.sum())
            prec = k_m/(k_m+k_b) if (k_m+k_b) else float("nan")
            out[model][c]=dict(
                malicious_flag_rate=wilson(k_m,len(mal)),
                benign_flag_rate=wilson(k_b,len(ben)),
                precision=round(prec,3),
                mal_score_mean=round(float(mal.raw_score.mean()),3),
                ben_score_mean=round(float(ben.raw_score.mean()),3))
    return out

# ---------------- T7: contract-level confusion deltas ----------------
def t7():
    out={}
    for c in ["M0","M3","F200"]:
        m0=sub("AuthGuard-M0",c).set_index("sample_id")
        ag=sub("AuthGuard-aug",c).set_index("sample_id")
        common=m0.index.intersection(ag.index)
        m0=m0.loc[common]; ag=ag.loc[common]
        mal=m0.true_label==1
        m0p=m0.predicted_label.astype(bool); agp=ag.predicted_label.astype(bool)
        both=int((mal & m0p & agp).sum())
        m0only=int((mal & m0p & ~agp).sum())
        agonly=int((mal & ~m0p & agp).sum())
        neither=int((mal & ~m0p & ~agp).sum())
        ben=~mal
        newfp=int((ben & ~m0p & agp).sum())     # benign newly flagged by aug
        fixed=int((ben & m0p & ~agp).sum())      # benign corrected by aug
        # singleton-family & family-macro recall (malicious only), aug vs m0
        def macro_recall(pred):
            r=[];
            dd=pd.DataFrame({"fam":m0["family_id"].values,"mal":mal.values,"hit":(mal.values&pred.values)})
            for fid,grp in dd[dd.mal].groupby("fam"):
                r.append(grp["hit"].sum()/len(grp))
            return round(float(np.mean(r)),3) if r else float("nan")
        def singleton_recall(pred):
            idx=mal.values & m0["family_id"].isin(SINGLETON).values
            return round(float((pred.values & idx).sum()/max(idx.sum(),1)),3)
        out[c]=dict(n_malicious=int(mal.sum()), both_detect=both, M0_only=m0only,
            aug_only=agonly, neither=neither, benign_newly_flagged_by_aug=newfp,
            benign_corrected_by_aug=fixed,
            singleton_recall_M0=singleton_recall(m0p), singleton_recall_aug=singleton_recall(agp),
            family_macro_recall_M0=macro_recall(m0p), family_macro_recall_aug=macro_recall(agp))
    return out

# ---------------- T8: paired bootstrap CIs (AG-M0 vs AG-aug) ----------------
def paired_boot(cond, nboot=5000):
    m0=sub("AuthGuard-M0",cond).set_index("sample_id")
    ag=sub("AuthGuard-aug",cond).set_index("sample_id")
    common=m0.index.intersection(ag.index)
    mal=common[m0.loc[common,"true_label"]==1]
    a=ag.loc[mal,"predicted_label"].values; b=m0.loc[mal,"predicted_label"].values
    diff=a.mean()-b.mean()
    n=len(mal); idx=np.arange(n); ds=[]
    for _ in range(nboot):
        s=rng.choice(idx,n,replace=True); ds.append(a[s].mean()-b[s].mean())
    lo,hi=np.percentile(ds,[2.5,97.5])
    # benign FPR paired diff
    ben=common[m0.loc[common,"true_label"]==0]
    af=ag.loc[ben,"predicted_label"].values; bf=m0.loc[ben,"predicted_label"].values
    return dict(cond=cond, n_mal=n, recall_M0=round(float(b.mean()),3), recall_aug=round(float(a.mean()),3),
        recall_diff_aug_minus_M0=round(float(diff),3), recall_diff_CI95=[round(float(lo),3),round(float(hi),3)],
        benign_FPR_M0=round(float(bf.mean()),3), benign_FPR_aug=round(float(af.mean()),3),
        benign_FPR_diff=round(float(af.mean()-bf.mean()),3))

def main():
    res=dict(T6_shortcut=t6(), T7_contract_level=t7(),
             T8_paired_bootstrap={c:paired_boot(c) for c in ["M0","M2","M3","F100","F200"]})
    json.dump(res, open(os.path.join(REP,"advtrain_analysis.json"),"w"), indent=2)
    # contract-level table CSV
    pd.DataFrame(res["T7_contract_level"]).T.to_csv(os.path.join(REP,"advtrain_contract_delta.csv"))

    print("=== T8 paired bootstrap (AuthGuard-aug - AuthGuard-M0), malicious recall ===")
    for c,d in res["T8_paired_bootstrap"].items():
        print(f"  {c:5s} recall {d['recall_M0']}->{d['recall_aug']} diff {d['recall_diff_aug_minus_M0']:+.3f} "
              f"CI{d['recall_diff_CI95']} | benignFPR {d['benign_FPR_M0']}->{d['benign_FPR_aug']} ({d['benign_FPR_diff']:+.3f})")
    print("\n=== T7 contract-level (AG-M0 vs AG-aug) ===")
    for c,d in res["T7_contract_level"].items():
        print(f"  [{c}] both={d['both_detect']} M0only={d['M0_only']} AUGonly={d['aug_only']} neither={d['neither']} "
              f"| benign +FP={d['benign_newly_flagged_by_aug']} fixed={d['benign_corrected_by_aug']} "
              f"| singleton rec {d['singleton_recall_M0']}->{d['singleton_recall_aug']} "
              f"macro {d['family_macro_recall_M0']}->{d['family_macro_recall_aug']}")
    print("\n=== T6 shortcut: benign flag rate rising with padding? ===")
    for m in ["AuthGuard-M0","AuthGuard-aug"]:
        row=" ".join(f"{c}:{res['T6_shortcut'][m][c]['benign_flag_rate'][0]}" for c in ["M0","F25","F50","F100","F200"])
        print(f"  {m:16s} benignFPR  {row}")

if __name__=="__main__":
    main()
