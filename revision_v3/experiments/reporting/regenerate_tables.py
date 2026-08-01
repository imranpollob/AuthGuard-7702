"""Part 16: regenerates provisional markdown tables from the real results JSON files produced
by Parts 6/7/8/9/10/13/14 under revision_v3/results/. Every table this script can source from
real data is written; tables requiring data this pipeline pass did not produce (e.g. a
completed 5-month/6-chain temporal collection) are written with an explicit
NOT_YET_AVAILABLE placeholder rather than fabricated numbers.

Every generated table is prefixed with the required provisional banner.

Usage:
    python3 revision_v3/experiments/reporting/regenerate_tables.py
"""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
RESULTS = os.path.join(V3, "results")
OUT_DIR = os.path.join(V3, "manuscript_assets", "provisional")
os.makedirs(OUT_DIR, exist_ok=True)

BANNER = "**PROVISIONAL — LLM REFERENCE LABELS. LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**\n\n"


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def write_table(name: str, lines: list[str]) -> None:
    path = os.path.join(OUT_DIR, name)
    with open(path, "w") as f:
        f.write(BANNER)
        f.write("\n".join(lines) + "\n")
    print(f"wrote {path}")


def table_gold_dev_baseline():
    d = load_json(os.path.join(RESULTS, "llm_provisional", "gold_dev_baseline", "gold_dev_baseline_report.json"))
    if not d:
        write_table("table_07_provisional_gold_dev_results.md", ["NOT_YET_AVAILABLE -- run Part 6."])
        return
    lines = ["# Table 7 — Provisional Gold-Dev Results", "",
             f"n_evaluated_binary={d['n_evaluated_binary']}, uncertain_coverage={d['uncertain_coverage_pct']}%",
             "", "| Model | AUPRC | AUROC | Precision | Recall | Specificity | FPR | F1 | Balanced Acc | Brier | ECE |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, m in d["models"].items():
        if "error" in m:
            continue
        lines.append(f"| {name} | {m['auprc']:.3f} | {m['auroc']:.3f} | {m['precision']:.3f} | "
                      f"{m['recall']:.3f} | {m['specificity']:.3f} | {m['fpr']:.3f} | {m['f1']:.3f} | "
                      f"{m['balanced_accuracy']:.3f} | {m['brier']:.3f} | {m['calibration_error']:.3f} |")
    r = d["source_static_rule"]
    lines.append(f"| source_static_rule | - | - | {r['precision']:.3f} | {r['recall']:.3f} | "
                  f"{r['specificity']:.3f} | {r['fpr']:.3f} | {r['f1']:.3f} | {r['balanced_accuracy']:.3f} | - | - |")
    write_table("table_07_provisional_gold_dev_results.md", lines)


def table_gold_test():
    d = load_json(os.path.join(RESULTS, "llm_provisional", "gold_test", "gold_test_report.json"))
    if not d:
        write_table("table_08_provisional_gold_test_results.md", ["NOT_YET_AVAILABLE -- run Part 9."])
        return
    lines = ["# Table 8 — Provisional Gold-Test Results", "",
             f"n_evaluated_binary={d['n_evaluated_binary']}, "
             f"uncertainty_exclusion_rate={d['uncertainty_exclusion_rate_pct']}%",
             "", "| Model | AUPRC | 95% CI | AUROC | Recall | FPR | F1 | Balanced Acc |",
             "|---|---|---|---|---|---|---|---|"]
    for name, aup in d["model_ranking_by_auprc"]:
        m = d["models"][name]
        lines.append(f"| {name} | {m['auprc']:.3f} | [{m['auprc_ci_95'][0]:.3f}, {m['auprc_ci_95'][1]:.3f}] | "
                      f"{m['auroc']:.3f} | {m['recall']:.3f} | {m['fpr']:.3f} | {m['f1']:.3f} | "
                      f"{m['balanced_accuracy']:.3f} |")
    r = d["source_static_rule"]
    lines.append(f"| source_static_rule | - | - | - | {r['recall']:.3f} | {r['fpr']:.3f} | "
                  f"{r['f1']:.3f} | {r['balanced_accuracy']:.3f} |")
    write_table("table_08_provisional_gold_test_results.md", lines)


def table_static_rule_and_cascade():
    d = load_json(os.path.join(RESULTS, "llm_provisional", "cascade", "cascade_report.json"))
    if not d:
        write_table("table_09_static_rule_comparison.md", ["NOT_YET_AVAILABLE -- run Part 10."])
        write_table("table_10_cascade_evaluation.md", ["NOT_YET_AVAILABLE -- run Part 10."])
        return
    gt = d["gold_test_frozen_policy_evaluation"]
    lines = ["# Table 10 — Cascade Evaluation (Gold-Test, frozen policy from Gold-Dev)", "",
             f"escalation band (from Gold-Dev): {d['escalation_band_selected_on_gold_dev_only']}", "",
             "| Policy | % Escalated | % Resolved Locally | Recall (UNSAFE coverage) | FNR | FPR |",
             "|---|---|---|---|---|---|"]
    for name, m in gt.items():
        if "confusion_matrix" in m:
            lines.append(f"| {name} | {m['pct_escalated']}% | {m['pct_resolved_locally']}% | "
                          f"{m['unsafe_coverage_recall']:.3f} | {m['false_negative_rate']:.3f} | "
                          f"{m['false_positive_rate']:.3f} |")
        else:
            lines.append(f"| {name} | {m['pct_escalated']}% | - | - | - | - |")
    write_table("table_10_cascade_evaluation.md", lines)


def table_deployment():
    d = load_json(os.path.join(RESULTS, "deployment", "deployment_report.json"))
    if not d:
        write_table("table_06_deployment_results.md", ["NOT_YET_AVAILABLE -- run Part 14."])
        return
    lines = ["# Table 6 — Deployment Evaluation", "",
             f"Hardware: {d['environment']['gpu_name']}, {d['environment']['hardware_cpu']}, "
             f"torch {d['environment']['torch_version']}", "",
             "| Model | Device | Params | Forward p50 (ms) | Forward p99 (ms) | E2E p50 (ms) | Throughput (items/s) |",
             "|---|---|---|---|---|---|---|"]
    for name, devs in d["models"].items():
        for dev_name, m in devs.items():
            if dev_name == "onnx":
                continue
            lines.append(f"| {name} | {dev_name} | {m['total_params']:,} | "
                          f"{m['forward_latency_ms']['median_ms']:.2f} | {m['forward_latency_ms']['p99_ms']:.2f} | "
                          f"{m['end_to_end_latency_ms']['median_ms']:.2f} | {m['batch_throughput_items_per_sec']:.1f} |")
        onnx = devs.get("onnx", {})
        if onnx.get("export_succeeded"):
            lines.append(f"| {name} | onnx-cpu | - | "
                          f"{onnx.get('onnx_cpu_latency_ms', {}).get('median_ms', float('nan')):.2f} | "
                          f"{onnx.get('onnx_cpu_latency_ms', {}).get('p99_ms', float('nan')):.2f} | - | - |")
    write_table("table_06_deployment_results.md", lines)


def table_legitimate_controls():
    path = os.path.join(V3, "external_controls", "verified_legitimate_controls.csv")
    if not os.path.exists(path):
        write_table("table_12_legitimate_control_evaluation.md", ["NOT_YET_AVAILABLE -- run Part 13."])
        return
    import csv
    from collections import Counter
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    dist = Counter(r["category"] for r in rows)
    lines = ["# Table 12 — Legitimate-Control Verification", "",
             f"n_deployments={len(rows)}",
             "", "| Category | Count |", "|---|---|"]
    for cat, n in dist.items():
        lines.append(f"| {cat} | {n} |")
    write_table("table_12_legitimate_control_evaluation.md", lines)


def table_temporal():
    d = load_json(os.path.join(RESULTS, "llm_provisional", "temporal", "temporal_report.json"))
    if not d or d.get("n_total_temporal_items", 0) == 0:
        write_table("table_11_temporal_evaluation.md", ["NOT_YET_AVAILABLE (or 0 items) -- run Part 11-12."])
        return
    lines = ["# Table 11 — Temporal Evaluation", "",
              f"n_total={d['n_total_temporal_items']}, "
              f"unseen_families={d['n_previously_unseen_family']}, "
              f"exact_duplicates={d['n_exact_historical_duplicate']}, "
              f"uncertain={d['n_uncertain']}", ""]
    if d.get("models"):
        lines += ["| Model | AUPRC | AUROC | ECE |", "|---|---|---|---|"]
        for name, m in d["models"].items():
            lines.append(f"| {name} | {m['auprc']:.3f} | {m['auroc']:.3f} | {m['calibration_error']:.3f} |")
    else:
        lines.append(d.get("note", ""))
    write_table("table_11_temporal_evaluation.md", lines)


def main() -> int:
    table_gold_dev_baseline()
    table_gold_test()
    table_static_rule_and_cascade()
    table_deployment()
    table_legitimate_controls()
    table_temporal()
    print(f"\nAll tables written to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
