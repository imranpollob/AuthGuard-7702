#!/usr/bin/env python3
"""Generate original-vs-task-aligned comparison and provenance reports."""
from __future__ import annotations

import hashlib
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "paper_build", "data_hygiene")


def load(path):
    return json.load(open(os.path.join(ROOT, path)))


def f(x):
    return f"{x:.3f}"


def delta(a, b):
    return f"{b-a:+.3f}"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def paired_shape():
    p = pd.read_csv(os.path.join(OUT, "task_aligned_paired_results.csv"))
    d = pd.read_csv(os.path.join(OUT, "task_aligned_dataset_v1.csv"))
    sizes = d[d["class"] == "malicious"].groupby("family_id").size()
    singleton = set(sizes[sizes == 1].index)
    out = {}
    for condition in ["M0", "M3", "F200"]:
        out[condition] = {}
        for model in ["AuthGuard-M0", "AuthGuard-aug"]:
            q = p[(p["condition"] == condition) & (p["model"] == model) &
                  (p["true_label"] == 1)]
            out[condition][model] = {
                "pooled_recall": float(q["predicted_label"].mean()),
                "singleton_recall": float(q[q["family_id"].isin(singleton)]["predicted_label"].mean()),
                "family_macro_recall": float(q.groupby("family_id")["predicted_label"].mean().mean()),
            }
    return out


def main():
    original_det = load("results/detection_results.json")
    ta_det = load("paper_build/data_hygiene/task_aligned_detection_results.json")
    original_mut = load("results/mutation_curve.json")
    ta_mut = load("paper_build/data_hygiene/task_aligned_mutation_curve.json")
    original_vol = load("results/mutation_volume.json")
    ta_vol = load("paper_build/data_hygiene/task_aligned_mutation_volume.json")
    original_adv = load("advtrain_results.json")["aggregate"]
    ta_adv = load("paper_build/data_hygiene/task_aligned_advtrain_results.json")["aggregate"]
    manifest = load("paper_build/data_hygiene/task_aligned_manifest_summary.json")
    shape = paired_shape()

    # Add paired family-shape results to the consolidated machine-readable output.
    consolidated_path = os.path.join(OUT, "task_aligned_results.json")
    consolidated = json.load(open(consolidated_path))
    consolidated["paired_family_shape"] = shape
    with open(consolidated_path, "w") as h:
        json.dump(consolidated, h, indent=2)

    lines = [
        "# Original versus Task-Aligned v1 Results",
        "",
        "The task-alignment policy and manifest were frozen and hashed before any rerun outcome "
        "was read. Original artifacts remain unchanged. Values below are fold means unless marked "
        "as pooled.",
        "",
        "## Cohort change",
        "",
        "| item | original | task-aligned v1 | change |",
        "|---|---:|---:|---:|",
        f"| all samples | 3,258 | {manifest['retained_rows']:,} | {manifest['retained_rows']-3258:+,} |",
        f"| malicious | 793 | {manifest['retained_class_counts']['malicious']:,} | {manifest['retained_class_counts']['malicious']-793:+,} |",
        f"| benign_cleared | 1,657 | {manifest['retained_class_counts']['benign_cleared']:,} | {manifest['retained_class_counts']['benign_cleared']-1657:+,} |",
        f"| benign_general | 800 | {manifest['retained_class_counts']['benign_general']:,} | {manifest['retained_class_counts']['benign_general']-800:+,} |",
        f"| benign_AA | 8 | {manifest['retained_class_counts']['benign_AA']:,} | {manifest['retained_class_counts']['benign_AA']-8:+,} |",
        f"| malicious-bearing families | 214 | {manifest['malicious_bearing_families']} | {manifest['malicious_bearing_families']-214:+d} |",
        "",
        "Designators: 32/76 runtimes recovered; 3 safely retained, 29 excluded as cross-family "
        "exact duplicates, and 44 excluded unresolved. Exact conflicts: all 23 hashes / 103 rows "
        "quarantined. The retained manifest has zero cross-class exact hashes.",
        "",
        "## G-DET",
        "",
        "| method | family AUPRC original | family AUPRC v1 | Δ | random AUPRC original | random AUPRC v1 | Δ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    methods = ["usenix_name_rule", "usenix_struct_rule", "blocklist", "selector_model",
               "opcode_rf", "opcode_xgb", "authguard"]
    names = {"usenix_name_rule": "sensitive-name approximation",
             "usenix_struct_rule": "external-call over-approximation",
             "blocklist": "blocklist", "selector_model": "selector-LR",
             "opcode_rf": "opcode-RF", "opcode_xgb": "opcode-XGB", "authguard": "AuthGuard"}
    for method in methods:
        of = original_det["primary_mal_vs_cleared"]["leave_family_out"][method]["mean"]["AUPRC"]
        tf = ta_det["primary_mal_vs_cleared"]["leave_family_out"][method]["mean"]["AUPRC"]
        or_ = original_det["primary_mal_vs_cleared"]["random_split"][method]["mean"]["AUPRC"]
        tr = ta_det["primary_mal_vs_cleared"]["random_split"][method]["mean"]["AUPRC"]
        lines.append(f"| {names[method]} | {f(of)} | {f(tf)} | {delta(of,tf)} | "
                     f"{f(or_)} | {f(tr)} | {delta(or_,tr)} |")
    of = original_det["primary_mal_vs_cleared"]["leave_family_out"]["authguard"]["mean"]["AUPRC"]
    tf = ta_det["primary_mal_vs_cleared"]["leave_family_out"]["authguard"]["mean"]["AUPRC"]
    or_ = original_det["primary_mal_vs_cleared"]["random_split"]["authguard"]["mean"]["AUPRC"]
    tr = ta_det["primary_mal_vs_cleared"]["random_split"]["authguard"]["mean"]["AUPRC"]
    lines += ["", f"AuthGuard random-minus-family gap: {f(or_-of)} → {f(tr-tf)} "
              f"(change {delta(or_-of,tr-tf)}).", "", "## G-MUT", "",
              "| method | tier | original recall | v1 recall | Δ |",
              "|---|---|---:|---:|---:|"]
    mut_methods = ["usenix_name_rule", "usenix_struct_rule", "blocklist",
                   "selector_model", "opcode_xgb", "authguard"]
    for method in mut_methods:
        for tier in ["M0", "M1", "M2", "M3"]:
            o = original_mut[method][tier]["mean"]; t = ta_mut[method][tier]["mean"]
            lines.append(f"| {names.get(method,method)} | {tier} | {f(o)} | {f(t)} | {delta(o,t)} |")

    lines += ["", "## G-VOL compound M3-style flooding", "",
              "| method | flood | original recall | v1 recall | Δ |",
              "|---|---:|---:|---:|---:|"]
    for method in ["opcode_xgb", "authguard"]:
        for frac in ["0.0", "0.25", "0.5", "1.0", "2.0"]:
            o = original_vol[method][frac]["mean"]; t = ta_vol[method][frac]["mean"]
            lines.append(f"| {names[method]} | +{int(float(frac)*100)}% | {f(o)} | {f(t)} | {delta(o,t)} |")

    lines += ["", "## G-ADV stricter validation protocol", "",
              "| model | condition | metric | original | v1 | Δ |",
              "|---|---|---|---:|---:|---:|"]
    for model in ["AuthGuard-M0", "AuthGuard-aug", "opcode-histogram XGBoost",
                  "opcode-histogram XGBoost-aug"]:
        for cond in ["M0", "M3", "F200"]:
            for metric in ["AUPRC", "recall", "FPR"]:
                o = original_adv[model][cond]["mean"][metric]
                t = ta_adv[model][cond]["mean"][metric]
                lines.append(f"| {model} | {cond} | {metric} | {f(o)} | {f(t)} | {delta(o,t)} |")

    lines += ["", "## Task-aligned pooled family-shape results", "",
              "| condition | model | pooled recall | singleton recall | family-macro recall |",
              "|---|---|---:|---:|---:|"]
    for cond in ["M0", "M3", "F200"]:
        for model in ["AuthGuard-M0", "AuthGuard-aug"]:
            z = shape[cond][model]
            lines.append(f"| {cond} | {model} | {f(z['pooled_recall'])} | "
                         f"{f(z['singleton_recall'])} | {f(z['family_macro_recall'])} |")

    lines += [
        "",
        "## Review conclusion",
        "",
        "The revised cohort changes several operating-point results materially. G-DET AuthGuard "
        "AUPRC increases, but G-MUT retained recall falls and the unaugmented G-ADV F200 recall "
        "falls sharply. Augmentation remains beneficial at F200 under fold-mean, pooled, singleton, "
        "family-macro, and family-clustered-bootstrap analyses. The old numerical headlines should "
        "therefore be replaced rather than combined with v1 values.",
    ]
    with open(os.path.join(OUT, "original_vs_task_aligned.md"), "w") as h:
        h.write("\n".join(lines) + "\n")

    artifacts = [
        "task_aligned_dataset_v1.csv", "designator_audit.csv", "conflicting_bytecodes.csv",
        "task_alignment_protocol.md", "task_alignment_protocol.sha256",
        "task_aligned_detection_results.json", "task_aligned_mutation_curve.json",
        "task_aligned_mutation_preservation.json", "task_aligned_mutation_volume.json",
        "task_aligned_advtrain_results.json", "task_aligned_paired_results.csv",
        "task_aligned_results.json", "task_aligned_advtrain_leakage_assertions.txt",
    ]
    prov = [
        "# Task-Aligned Result Provenance",
        "",
        "## Protocol identity",
        "",
        f"- Frozen task-alignment protocol SHA-256: `{open(os.path.join(OUT,'task_alignment_protocol.sha256')).read().split()[0]}`.",
        "- Original family IDs retained without reclustering.",
        "- Original primary and secondary outer family-to-fold identities stored in the manifest.",
        "- Random diagnostic mechanically reruns the same seeded KFold on the reduced row order.",
        "- Feature extraction, estimators, seeds, thresholds, mutations, augmentation, and weighting are unchanged.",
        "",
        "## Output fingerprints",
        "",
        "| artifact | SHA-256 |",
        "|---|---|",
    ]
    for name in artifacts:
        path = os.path.join(OUT, name)
        prov.append(f"| `{name}` | `{sha(path)}` |")
    prov += [
        "",
        "## Group provenance",
        "",
        "- **G-DET:** imported the frozen detector implementation; fixed family tests come from stored original fold IDs; in-sample training thresholds unchanged.",
        "- **G-MUT:** learned models fit on retained M0 training folds; only retained held-out positives mutated; all variants inherit original families.",
        "- **G-VOL:** unchanged compound metadata/address/selector transformation with variable appended dead code.",
        "- **G-ADV:** original test fold `f`, validation fold `(f+1) mod 5`, and remaining train-fit folds; unchanged seen/held-out conditions and source weights.",
        "",
        "## Integrity assertions",
        "",
        "- Zero cross-class exact hashes after cleaning.",
        "- Zero retained exact hashes spanning frozen families.",
        "- Zero families spanning primary or secondary stored outer folds.",
        "- All task-aligned G-ADV source/family/train-test-hash and mutant-inheritance assertions passed.",
        "- G-MUT preservation checks cover all 727 retained positives at M1, M2, and M3.",
        "",
        "## Aggregation",
        "",
        "Main tables use arithmetic means over the five preserved outer test folds and population SD. Paired analyses pool each contract’s one outer-test prediction and preserve model pairing. Family-clustered uncertainty is separately recorded under `paper_build/statistics/`.",
    ]
    with open(os.path.join(OUT, "task_aligned_result_provenance.md"), "w") as h:
        h.write("\n".join(prov) + "\n")


if __name__ == "__main__":
    main()
