#!/usr/bin/env python3
"""
06_figures.py -- publication-ready figures (Task F).
  fig_family_size.png        malicious family-size distribution (Claim 2)
  fig_random_vs_family.png   LFO-vs-random AUPRC gap per method (leakage context)
  fig_mutation_curve.png     retained-detection M0->M3 per method (Claim 3, headline)
  fig_mutation_volume.png    dead-code volume sweep (robustness limit)
  fig_auprc.png              per-method AUPRC under LFO (primary task, Claim 1/tool)
All figures use a CVD-validated categorical palette + marker/linestyle secondary encoding.
"""
import os, sys, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)

# CVD-validated categorical palette (fixed assignment per method entity)
CLR = {
    "authguard":          "#2a78d6",  # blue (hero)
    "opcode_xgb":         "#1baf7a",  # aqua
    "opcode_rf":          "#199e70",
    "selector_model":     "#eda100",  # yellow
    "usenix_name_rule":   "#e34948",  # red
    "usenix_struct_rule": "#4a3aa7",  # violet
    "blocklist":          "#eb6834",  # orange
    "usenix_shipped_oracle": "#52514e",
}
MRK = {"authguard": "o", "opcode_xgb": "s", "opcode_rf": "s", "selector_model": "D",
       "usenix_name_rule": "^", "usenix_struct_rule": "v", "blocklist": "X",
       "usenix_shipped_oracle": "P"}
LBL = {"authguard": "AuthGuard", "opcode_xgb": "opcode-XGB", "opcode_rf": "opcode-RF",
       "selector_model": "selector-LR", "usenix_name_rule": "USENIX name-rule",
       "usenix_struct_rule": "USENIX struct-rule", "blocklist": "blocklist (hash)",
       "usenix_shipped_oracle": "USENIX shipped (oracle)"}

plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 140})


def fig_family_size():
    fz = pd.read_csv(os.path.join(ROOT, "family_assignment_frozen.csv"))
    mal = fz[fz["class"] == "malicious"]
    sizes = mal.groupby("family_id").size().sort_values(ascending=False).values
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.bar(range(1, len(sizes) + 1), sizes, color="#2a78d6", width=1.0)
    ax.set_yscale("log")
    ax.set_xlabel("malicious family rank (by size)")
    ax.set_ylabel("contracts in family (log)")
    ax.set_title(f"Malicious delegate family-size distribution\n"
                 f"{len(mal)} contracts, {len(sizes)} families, "
                 f"{(sizes==1).sum()} singletons ({100*(sizes==1).mean():.0f}%), largest={sizes.max()}")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_family_size.png")); plt.close(fig)


def fig_random_vs_family():
    d = json.load(open(os.path.join(RES, "detection_results.json")))
    task = d["primary_mal_vs_cleared"]
    methods = ["usenix_name_rule", "blocklist", "selector_model", "opcode_rf",
               "opcode_xgb", "authguard"]
    lfo = [task["leave_family_out"][m]["mean"]["AUPRC"] for m in methods]
    rnd = [task["random_split"][m]["mean"]["AUPRC"] for m in methods]
    x = np.arange(len(methods)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    b1 = ax.bar(x - w/2, lfo, w, label="leave-family-out (honest)", color="#2a78d6")
    b2 = ax.bar(x + w/2, rnd, w, label="random split (leaks)", color="#eb6834")
    for b in list(b1) + list(b2):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.01, f"{b.get_height():.2f}",
                ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels([LBL[m] for m in methods], rotation=25, ha="right")
    ax.set_ylabel("AUPRC"); ax.set_ylim(0, 1.05)
    ax.set_title("Random splits inflate AUPRC — the leakage every prior split hides\n(primary task: malicious vs benign_cleared)")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_random_vs_family.png")); plt.close(fig)


def fig_auprc():
    d = json.load(open(os.path.join(RES, "detection_results.json")))
    task = d["primary_mal_vs_cleared"]["leave_family_out"]
    methods = ["usenix_name_rule", "usenix_struct_rule", "blocklist", "selector_model",
               "opcode_rf", "opcode_xgb", "authguard"]
    vals = [task[m]["mean"]["AUPRC"] for m in methods]
    errs = [task[m]["std"]["AUPRC"] for m in methods]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.bar([LBL[m] for m in methods], vals, yerr=errs, capsize=4,
                  color=[CLR[m] for m in methods])
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, v+0.015, f"{v:.2f}", ha="center", fontsize=8)
    ax.axhline(0.324, ls="--", color="#52514e", lw=1)
    ax.text(0.1, 0.34, "base rate (0.32)", fontsize=8, color="#52514e")
    ax.set_ylabel("AUPRC (mean ± std, 5 family folds)"); ax.set_ylim(0, 1.0)
    ax.set_xticklabels([LBL[m] for m in methods], rotation=25, ha="right")
    ax.set_title("Detection under leave-family-out (primary task)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_auprc.png")); plt.close(fig)


def fig_mutation_curve():
    d = json.load(open(os.path.join(RES, "mutation_curve.json")))
    tiers = ["M0", "M1", "M2", "M3"]
    xt = ["M0\noriginal", "M1\nmetadata", "M2\n+addr/deadcode", "M3\n+selector rename"]
    methods = ["authguard", "opcode_xgb", "selector_model", "usenix_struct_rule",
               "usenix_name_rule", "blocklist"]
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    x = np.arange(len(tiers))
    for m in methods:
        y = [d[m][t]["mean"] for t in tiers]
        e = [d[m][t]["std"] for t in tiers]
        ax.errorbar(x, y, yerr=e, marker=MRK[m], color=CLR[m], lw=2, ms=8,
                    capsize=3, label=LBL[m])
        ax.annotate(f"{y[-1]:.2f}", (x[-1], y[-1]), textcoords="offset points",
                    xytext=(8, 0), fontsize=8, color=CLR[m])
    ax.set_xticks(x); ax.set_xticklabels(xt)
    ax.set_ylabel("retained detection (recall on held-out malicious)")
    ax.set_ylim(-0.03, 1.05)
    ax.set_title("Retained detection under semantics-preserving mutation\n"
                 "(held-out malicious; split before mutation; 793/793 preservation-verified)")
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="center left")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_mutation_curve.png")); plt.close(fig)


def fig_mutation_volume():
    d = json.load(open(os.path.join(RES, "mutation_volume.json")))
    fracs = ["0.0", "0.25", "0.5", "1.0", "2.0"]
    xlab = ["+0%", "+25%", "+50%", "+100%", "+200%"]
    methods = ["authguard", "opcode_xgb", "usenix_struct_rule", "usenix_name_rule"]
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    x = np.arange(len(fracs))
    for m in methods:
        y = [d[m][f]["mean"] for f in fracs]
        ax.plot(x, y, marker=MRK[m], color=CLR[m], lw=2, ms=8, label=LBL[m])
        ax.annotate(f"{y[-1]:.2f}", (x[-1], y[-1]), textcoords="offset points",
                    xytext=(8, 0), fontsize=8, color=CLR[m])
    ax.set_xticks(x); ax.set_xticklabels(xlab)
    ax.set_xlabel("appended unreachable (dead) code, as % of original ops")
    ax.set_ylabel("retained detection (recall)")
    ax.set_ylim(-0.03, 1.05)
    ax.set_title("Robustness limit: dead-code flooding on top of M3\n"
                 "AuthGuard's n-gram features dilute under heavy padding (honest limitation)")
    ax.legend(frameon=False, fontsize=9, loc="center left")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_mutation_volume.png")); plt.close(fig)


def main():
    fig_family_size(); print("[fig] fig_family_size.png")
    fig_random_vs_family(); print("[fig] fig_random_vs_family.png")
    fig_auprc(); print("[fig] fig_auprc.png")
    fig_mutation_curve(); print("[fig] fig_mutation_curve.png")
    fig_mutation_volume(); print("[fig] fig_mutation_volume.png")


if __name__ == "__main__":
    main()
