#!/usr/bin/env python3
"""Regenerate manuscript result tables from machine-readable v2 outputs."""
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


def row(*cells):
    return " & ".join(str(c) for c in cells) + r" \\"


def seeded_auprc(entry):
    """Primary-seed fold mean plus the approved stochastic-seed sensitivity range."""
    point = entry["mean"]["AUPRC"]
    values = [v["mean"]["AUPRC"] for v in entry.get("seedwise", {}).values()]
    if len(values) > 1:
        return f"{L(point)} [{L(min(values))}--{L(max(values))}]"
    return L(point)


def gdet_table():
    r = json.load(open(os.path.join(R, "gdet_v2", "gdet_v2_results.json")))["primary"]
    boot = json.load(open(os.path.join(R, "uncertainty", "gdet_bootstrap.json")))
    lfo, rnd = r["leave_family_out"], r["random_split"]
    order = [("authguard", "AuthGuard"), ("opcode_xgb", "opcode-hist XGBoost"),
             ("opcode_rf", "opcode-hist RF"), ("selector_model", "selector LR"),
             ("usenix_name_rule", "sensitive-name approx"),
             ("usenix_struct_rule", "external-call over-approx"),
             ("blocklist", "exact-hash blocklist")]
    lines = [r"\begin{tabular}{lcccccc}", r"\toprule",
             row("Method", "AUPRC (fam)", "AUROC", "F1", "Prec", "Rec", "FPR"),
             r"\midrule"]
    for key, name in order:
        m, s = lfo[key]["mean"], lfo[key]["std"]
        lines.append(row(name, f"{L(m['AUPRC'])}$\\pm${L(s['AUPRC'])}", L(m["AUROC"]),
                         L(m["F1"]), L(m["Precision"]), L(m["Recall"]), L(m["FPR"])))
    lines += [r"\midrule",
              row("AuthGuard (random split)", L(rnd["authguard"]["mean"]["AUPRC"]),
                  L(rnd["authguard"]["mean"]["AUROC"]), "---", "---", "---", "---"),
              r"\bottomrule", r"\end{tabular}"]
    prov = f"% AuthGuard AUPRC bootstrap CI {boot['authguard_AUPRC']['CI95']}; " \
           f"AG-vs-{boot['authguard_minus_strongest_baseline']['baseline']} " \
           f"delta {L(boot['authguard_minus_strongest_baseline']['delta_point'])} " \
           f"CI {boot['authguard_minus_strongest_baseline']['delta_CI95']}"
    return "\n".join(lines) + "\n" + prov + "\n", "gdet_v2_results.json + gdet_bootstrap.json"


def gmut_table():
    r = json.load(open(os.path.join(R, "gmut_v2", "gmut_v2_results.json")))["results"]["iso"]
    lines = [r"\begin{tabular}{lccccc}", r"\toprule",
             row("Method", "M0", "M1", "M2", "M3", "metric"), r"\midrule"]
    for key, name in [("authguard", "AuthGuard"), ("opcode_xgb", "opcode-hist XGB"),
                      ("usenix_name_rule", "sensitive-name"),
                      ("usenix_struct_rule", "external-call")]:
        rec = [L(r[key][tier]["recall"]["mean"]) for tier in ["M0", "M1", "M2", "M3"]]
        lines.append(row(name, *rec, "recall"))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "gmut_v2_results.json (iso arm)"


def gvol_table():
    r = json.load(open(os.path.join(R, "gvol_v2", "gvol_v2_results.json")))["results"]["iso"]
    fractions = ["0.0", "0.25", "0.5", "1.0", "2.0"]
    lines = [r"\begin{tabular}{lccccc}", r"\toprule",
             row("Method", "+0\\%", "+25\\%", "+50\\%", "+100\\%", "+200\\%"),
             r"\midrule"]
    for key, name in [("authguard", "AuthGuard"), ("opcode_xgb", "opcode-hist XGB")]:
        lines.append(row(name, *[L(r[key][f]["recall"]["mean"]) for f in fractions]))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "gvol_v2_results.json (iso multi-donor arm)"


def gadv_table():
    p = os.path.join(R, "gadv_v2", "gadv_v2_results.json")
    if not os.path.exists(p):
        return None, None
    agg = json.load(open(p))["aggregate"]["val_threshold"]
    conditions = ["M0", "M3", "F200", "M3F200"]
    lines = [r"\begin{tabular}{lcccc}", r"\toprule", row("Model", *conditions),
             r"\midrule"]
    for key in ["AuthGuard-M0", "AuthGuard-aug", "opcode-histogram XGBoost",
                "opcode-histogram XGBoost-aug"]:
        lines.append(row(key, *[L(agg[key][c]["mean"]["Recall"]) for c in conditions]))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "gadv_v2_results.json (donor-isolated val-threshold arm)"


def baselines_table():
    bp, ap = (os.path.join(R, "baselines", "baselines_results.json"),
              os.path.join(R, "ablations", "ablations_results.json"))
    if not os.path.exists(bp) or not os.path.exists(ap):
        return None, None
    b, a = json.load(open(bp)), json.load(open(ap))
    lines = [r"\begin{tabular}{lccc}", r"\toprule",
             row("Representation / model", "Dim.", "AUPRC (seed [range])", "FPR"),
             r"\midrule"]
    for key, label, dim in [("hash_xgb", "hashed 4-gram XGB", "512"),
                            ("tfidf_lr", "TF--IDF LR", "$\\leq$20k"),
                            ("tfidf_svm", "TF--IDF SVM", "$\\leq$20k")]:
        m = b[key]["mean"]
        lines.append(row(label, dim, seeded_auprc(b[key]), L(m["FPR"])))
    lines.append(r"\midrule")
    for key, label in [("struct_sel_only", "structural/selector only"),
                       ("hist_only", "opcode histogram only"),
                       ("ngram_only", "hashed 4-gram only"),
                       ("hist_struct", "histogram + structural"),
                       ("hist_ngram", "histogram + 4-gram"),
                       ("full_773", "AuthGuard full"),
                       ("no_selectors", "full without selector features"),
                       ("no_length", "full without explicit length"),
                       ("no_length_metadata", "full without length/metadata")]:
        m = a[key]["mean"]
        lines.append(row(label, a[key]["dimensions"], seeded_auprc(a[key]), L(m["FPR"])))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "baselines_results.json + ablations_results.json"


def first_stop_table():
    p = os.path.join(R, "first_stop", "first_stop_results.json")
    if not os.path.exists(p):
        return None, None
    r = json.load(open(p)); primary = r["primary_stored_folds"]
    boot = r["paired_family_clustered_bootstrap"]
    lines = [r"\begin{tabular}{lccc}", r"\toprule",
             row("Representation", "Dim.", "AUPRC (seed [range])",
                 "$\\Delta$ vs full (95\\% CI)"), r"\midrule"]
    for key, label in [("first_stop_full_773", "first-STOP full"),
                       ("first_stop_no_length", "first-STOP no length"),
                       ("first_stop_no_length_metadata", "first-STOP no length/metadata")]:
        m = primary[key]; b = boot[f"{key}_minus_authguard_full_773"]; ci = b["delta_CI95"]
        delta = f"{b['delta_point']:+.3f} [{ci[0]:+.3f},{ci[1]:+.3f}]"
        lines.append(row(label, m["dimensions"], seeded_auprc(m), delta))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "first_stop_results.json"


def sensitivity_table():
    p = os.path.join(R, "family_sensitivity", "family_sensitivity.json")
    if not os.path.exists(p):
        return None, None
    r = json.load(open(p))["primary_track"]
    lines = [r"\begin{tabular}{lccc}", r"\toprule",
             row("Family threshold", "AuthGuard AUPRC", "Opcode-XGB AUPRC", "Gap"),
             r"\midrule"]
    for threshold in ["0.75", "0.85", "0.90"]:
        ag = r[threshold]["authguard"]["family_AUPRC_mean"]
        op = r[threshold]["opcode_xgb"]["family_AUPRC_mean"]
        lines.append(row(threshold, L(ag), L(op), L(ag - op)))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "family_sensitivity.json (primary frozen-family track)"


def controls_table():
    p = os.path.join(R, "secondary_controls", "secondary_controls.json")
    if not os.path.exists(p):
        return None, None
    r = json.load(open(p))["benign_general"]
    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             row("Model", "Flags / 797", "FPR", "Alerts / 1,000"), r"\midrule"]
    for key, label in [("authguard", "AuthGuard"), ("opcode_rf", "opcode RF"),
                       ("opcode_xgb", "opcode XGB")]:
        m = r[key]
        lines.append(row(label, m["flagged"], L(m["FPR"]), L(m["alerts_per_1000"], 0)))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", "secondary_controls.json"


def main():
    os.makedirs(OUT, exist_ok=True)
    provenance = {}
    generators = [("gdet", gdet_table), ("gmut", gmut_table), ("gvol", gvol_table),
                  ("gadv", gadv_table), ("baselines_ablations", baselines_table),
                  ("first_stop", first_stop_table), ("family_sensitivity", sensitivity_table),
                  ("secondary_controls", controls_table)]
    for name, fn in generators:
        tex, source = fn()
        if tex is None:
            continue
        with open(os.path.join(OUT, f"{name}_v2.tex"), "w") as f:
            f.write(tex)
        provenance[f"{name}_v2.tex"] = source
    with open(os.path.join(OUT, "numbers_provenance.json"), "w") as f:
        json.dump(provenance, f, indent=2)
    print(f"[tables] wrote {len(provenance)} tables -> {OUT}")


if __name__ == "__main__":
    main()
