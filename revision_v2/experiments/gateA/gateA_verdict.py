#!/usr/bin/env python3
"""Evaluate Gate A against the frozen success criteria (gateA_success_criteria.md)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import RV2  # noqa: E402

OUT = os.path.join(RV2, "results", "gateA")


def main():
    r = json.load(open(os.path.join(OUT, "gateA_results.json")))["results"]
    full, dual, fs = r["full"], r["dual"], r["first_stop"]
    checks = {}
    # 1. flooding improvement >= 0.10 over full-view on F200 or M3F200
    imp_f200 = dual["robustness"]["F200"]["recall_mean"] - full["robustness"]["F200"]["recall_mean"]
    imp_comp = dual["robustness"]["M3F200"]["recall_mean"] - full["robustness"]["M3F200"]["recall_mean"]
    checks["c1_flooding_improvement>=0.10"] = bool(imp_f200 >= 0.10 or imp_comp >= 0.10)
    # 2. clean AUPRC degradation <= 0.02
    clean_deg = full["cleanM0"]["family_AUPRC_mean"] - dual["cleanM0"]["family_AUPRC_mean"]
    checks["c2_clean_degradation<=0.02"] = bool(clean_deg <= 0.02)
    # 3. benign_general FPR increase <= 0.01
    fpr_inc = dual["cleanM0"]["benign_general_FPR_mean"] - full["cleanM0"]["benign_general_FPR_mean"]
    checks["c3_benign_FPR_increase<=0.01"] = bool(fpr_inc <= 0.01)
    # 4. consistency: positive improvement in >=4/5 folds on the winning condition
    cond = "F200" if imp_f200 >= imp_comp else "M3F200"
    per_fold = [d - fu for d, fu in zip(dual["robustness"][cond]["folds"],
                                        full["robustness"][cond]["folds"])]
    checks["c4_consistency>=4of5"] = bool(sum(x > 0 for x in per_fold) >= 4)
    # 5. beats first-STOP heuristic: >= 0.05 improvement on the winning condition
    imp_vs_fs = dual["robustness"][cond]["recall_mean"] - fs["robustness"][cond]["recall_mean"]
    dominates = (dual["cleanM0"]["family_AUPRC_mean"] >= fs["cleanM0"]["family_AUPRC_mean"] and
                 dual["robustness"][cond]["recall_mean"] >= fs["robustness"][cond]["recall_mean"])
    checks["c5_beats_first_stop"] = bool(imp_vs_fs >= 0.05 or dominates)

    verdict = "PASS" if all(checks.values()) else "FAIL"
    out = dict(verdict=verdict, checks=checks,
               metrics=dict(clean_AUPRC=dict(full=full["cleanM0"]["family_AUPRC_mean"],
                                             dual=dual["cleanM0"]["family_AUPRC_mean"],
                                             first_stop=fs["cleanM0"]["family_AUPRC_mean"]),
                            F200_recall=dict(full=full["robustness"]["F200"]["recall_mean"],
                                             dual=dual["robustness"]["F200"]["recall_mean"],
                                             first_stop=fs["robustness"]["F200"]["recall_mean"]),
                            M3F200_recall=dict(full=full["robustness"]["M3F200"]["recall_mean"],
                                               dual=dual["robustness"]["M3F200"]["recall_mean"],
                                               first_stop=fs["robustness"]["M3F200"]["recall_mean"]),
                            benign_FPR=dict(full=full["cleanM0"]["benign_general_FPR_mean"],
                                            dual=dual["cleanM0"]["benign_general_FPR_mean"]),
                            winning_condition=cond, improvement_f200=imp_f200,
                            improvement_compound=imp_comp))
    with open(os.path.join(OUT, "gateA_verdict.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
