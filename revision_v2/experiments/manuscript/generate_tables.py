#!/usr/bin/env python3
"""Phase 6C — regenerate all manuscript result tables from machine-readable v2 outputs.

Every number in the emitted .tex traces to a JSON produced by the v2 pipeline. No hand-typed
result values. Emits revision_v2/manuscript/tables/*.tex and a numbers_provenance.json mapping
each table cell group to its source file.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from harness import RV2  # noqa: E402

R = os.path.join(RV2, "results")
OUT = os.path.join(RV2, "manuscript", "tables")


def L(x, d=3):
    return f"{x:.{d}f}"


def gdet_table():
    r = json.load(open(os.path.join(R, "gdet_v2", "gdet_v2_results.json")))["primary"]
    boot = json.load(open(os.path.join(R, "uncertainty", "gdet_bootstrap.json")))
    lfo, rnd = r["leave_family_out"], r["random_split"]
    order = [("authguard", "AuthGuard"), ("opcode_xgb", "opcode-hist XGBoost"),
             ("opcode_rf", "opcode-hist RF"), ("selector_model", "selector LR"),
             ("usenix_name_rule", "sensitive-name approx"),
             ("usenix_struct_rule", "external-call over-approx"), ("blocklist", "exact-hash blocklist")]
    lines = [r"\begin{tabular}{lcccccc}", r"\toprule",
             r"Method & AUPRC (fam) & AUROC & F1 & Prec & Rec & FPR \\", r"\midrule"]
    for k, name in order:
        m = lfo[k]["mean"]; s = lfo[k]["std"]
        lines.append(f"{name} & {L(m['AUPRC'])}$\\pm${L(s['AUPRC'])} & {L(m['AUROC'])} & "
                     f"{L(m['F1'])} & {L(m['Precision'])} & {L(m['Recall'])} & {L(m['FPR'])} \\\\")
    lines += [r"\midrule",
              f"AuthGuard (random split) & {L(rnd['authguard']['mean']['AUPRC'])} & "
              f"{L(rnd['authguard']['mean']['AUROC'])} & --- & --- & --- & --- \\\\",
              r"\bottomrule", r"\end{tabular}"]
    prov = f"% AuthGuard AUPRC bootstrap CI {boot['authguard_AUPRC']['CI95']}; " \
           f"AG-vs-{boot['authguard_minus_strongest_baseline']['baseline']} " \
           f"delta {L(boot['authguard_minus_strongest_baseline']['delta_point'])} " \
           f"CI {boot['authguard_minus_strongest_baseline']['delta_CI95']}"
    return "\n".join(lines) + "\n" + prov + "\n", "gdet_v2_results.json + gdet_bootstrap.json"


def gmut_table():
    r = json.load(open(os.path.join(R, "gmut_v2", "gmut_v2_results.json")))["results"]["iso"]
    lines = [r"\begin{tabular}{lccccc}", r"\toprule",
             r"Method & M0 & M1 & M2 & M3 & (metric) \\", r"\midrule"]
    for k, name in [("authguard", "AuthGuard"), ("opcode_xgb", "opcode-hist XGB"),
                    ("usenix_name_rule", "sensitive-name"), ("usenix_struct_rule", "external-call")]:
        rec = [L(r[k][t]["recall"]["mean"]) for t in ["M0", "M1", "M2", "M3"]]
        lines.append(f"{name} & {rec[0]} & {rec[1]} & {rec[2]} & {rec[3]} & recall \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "gmut_v2_results.json (iso arm)"


def gvol_table():
    r = json.load(open(os.path.join(R, "gvol_v2", "gvol_v2_results.json")))["results"]["iso"]
    fr = ["0.0", "0.25", "0.5", "1.0", "2.0"]
    lines = [r"\begin{tabular}{lccccc}", r"\toprule",
             r"Method & +0\% & +25\% & +50\% & +100\% & +200\% \\", r"\midrule"]
    for k, name in [("authguard", "AuthGuard"), ("opcode_xgb", "opcode-hist XGB")]:
        rec = [L(r[k][f]["recall"]["mean"]) for f in fr]
        lines.append(f"{name} & " + " & ".join(rec) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "gvol_v2_results.json (iso multi-donor arm)"


def gadv_table():
    if not os.path.exists(os.path.join(R, "gadv_v2", "gadv_v2_results.json")):
        return None, None
    agg = json.load(open(os.path.join(R, "gadv_v2", "gadv_v2_results.json")))["aggregate"]["val_threshold"]
    conds = ["M0", "M3", "F200", "M3F200"]
    lines = [r"\begin{tabular}{lcccc}", r"\toprule",
             r"Model & " + " & ".join(conds) + r" \\ (recall) \midrule"]
    for k in ["AuthGuard-M0", "AuthGuard-aug", "opcode-histogram XGBoost",
              "opcode-histogram XGBoost-aug"]:
        rec = [L(agg[k][c]["mean"]["Recall"]) for c in conds]
        lines.append(f"{k} & " + " & ".join(rec) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "gadv_v2_results.json (donor-isolated, val-threshold arm)"


def main():
    os.makedirs(OUT, exist_ok=True)
    prov = {}
    for name, fn in [("gdet", gdet_table), ("gmut", gmut_table), ("gvol", gvol_table),
                     ("gadv", gadv_table)]:
        tex, src = fn()
        if tex is None:
            continue
        with open(os.path.join(OUT, f"{name}_v2.tex"), "w") as f:
            f.write(tex)
        prov[f"{name}_v2.tex"] = src
    with open(os.path.join(OUT, "numbers_provenance.json"), "w") as f:
        json.dump(prov, f, indent=2)
    print(f"[tables] wrote {len(prov)} tables -> {OUT}")


if __name__ == "__main__":
    main()
