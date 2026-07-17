#!/usr/bin/env python3
"""Static LaTeX and numerical-provenance audit for the extended paper."""

from collections import defaultdict
import csv
import json
from pathlib import Path
import re
import statistics
import sys


HERE = Path(__file__).resolve().parent
RV2 = HERE.parent
RESULTS = RV2 / "results"


def fail(message, failures):
    failures.append(message)


def close(actual, expected, tolerance=5e-7):
    return abs(float(actual) - float(expected)) <= tolerance


def main():
    failures = []
    main_text = (HERE / "main.tex").read_text()
    combined = main_text

    for item in re.findall(r"\\input\{([^}]+)\}", main_text):
        path = HERE / (item if item.endswith(".tex") else item + ".tex")
        if not path.exists():
            fail(f"missing input: {item}", failures)
        else:
            combined += "\n" + path.read_text()

    for item in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", main_text):
        if not (HERE / item).exists():
            fail(f"missing graphic: {item}", failures)

    if not (HERE / "references.bib").exists():
        fail("missing references.bib", failures)

    # Bounded syntax checks: braces, labels, references, and citation keys.
    code = "\n".join(re.split(r"(?<!\\)%", line, maxsplit=1)[0]
                     for line in combined.splitlines())
    code = code.replace(r"\{", "").replace(r"\}", "")
    balance = minimum = 0
    for char in code:
        if char == "{":
            balance += 1
        elif char == "}":
            balance -= 1
            minimum = min(minimum, balance)
    if balance or minimum < 0:
        fail(f"unbalanced braces: final={balance}, minimum={minimum}", failures)

    labels = re.findall(r"\\label\{([^}]+)\}", combined)
    refs = re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", combined)
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        fail(f"duplicate labels: {duplicates}", failures)
    missing_refs = sorted(set(refs) - set(labels))
    if missing_refs:
        fail(f"undefined references: {missing_refs}", failures)

    citations = set()
    for group in re.findall(r"\\cite\{([^}]+)\}", combined):
        citations.update(key.strip() for key in group.split(","))
    bib_text = (HERE / "references.bib").read_text()
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib_text))
    if citations - bib_keys:
        fail(f"undefined citations: {sorted(citations - bib_keys)}", failures)

    forbidden = (
        "production-ready",
        "first eip-7702 detector overall",
        "proves semantic equivalence",
        "guaranteed end-to-end",
        "without degrading the user experience",
    )
    for phrase in forbidden:
        if phrase in main_text.lower():
            fail(f"forbidden overclaim: {phrase}", failures)

    if r"\author{\IEEEauthorblockN{Anonymous Authors}}" not in main_text:
        fail("anonymous author block missing", failures)

    # Verify the headline aggregates directly from per-fold metrics.
    grouped = defaultdict(list)
    metric_path = RESULTS / "authguard_fusion" / "metrics.csv"
    with metric_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["seed"], row["model"], row["condition"])
            grouped[key].append(row)

    expected = {
        ("sequence_only", "cleanM0", "AUPRC"): 0.930900936168527,
        ("hist_ngram_xgb", "cleanM0", "AUPRC"): 0.8275898793230458,
        ("sequence_only", "F200", "AUPRC"): 0.9103805289040487,
        ("hist_ngram_xgb", "F200", "AUPRC"): 0.5765066938211997,
        ("sequence_only", "M3F200", "AUPRC"): 0.9101915525287843,
        ("hist_ngram_xgb", "M3F200", "AUPRC"): 0.5632513475793992,
        ("sequence_only", "cleanM0", "Recall_05"): 0.8281529441093763,
        ("sequence_only", "benign_general", "FPR_05"): 0.06161591466206497,
    }
    for (model, condition, metric), target in expected.items():
        seed_means = []
        for seed in ("7702", "7703", "7704"):
            values = [float(row[metric]) for row in grouped[(seed, model, condition)]
                      if row.get(metric) not in (None, "")]
            seed_means.append(statistics.fmean(values))
        actual = statistics.fmean(seed_means)
        if not close(actual, target):
            fail(f"aggregate mismatch {model}/{condition}/{metric}: {actual} != {target}",
                 failures)

    paired = json.loads((RESULTS / "authguard_fusion" /
                         "paired_family_bootstrap_sequence_only.json").read_text())
    if not close(paired["conditions"]["cleanM0"]["metrics"]["AUPRC"]["delta"],
                 0.057055206431399386):
        fail("clean paired AUPRC delta mismatch", failures)
    if not close(paired["conditions"]["F200"]["metrics"]["Recall_05"]["delta"],
                 0.5804676753782668):
        fail("F200 paired recall delta mismatch", failures)

    runtime = json.loads((RESULTS / "authguard_fusion" / "runtime_sequence.json").read_text())
    if runtime["model_bytes"] != 742561:
        fail("model byte count mismatch", failures)
    if not close(runtime["wall_milliseconds"]["mean"], 4.333623787333333):
        fail("runtime mean mismatch", failures)

    benchmark = json.loads((RESULTS / "authguard_bench" / "benchmark_summary.json").read_text())
    for key, value in (("rows", 3082), ("primary_rows", 2280),
                       ("primary_family_count", 819), ("unique_bytecode_count", 2528)):
        if benchmark[key] != value:
            fail(f"benchmark summary mismatch: {key}", failures)

    payload = {
        "pass": not failures,
        "tex_files_checked": 1 + len(re.findall(r"\\input\{([^}]+)\}", main_text)),
        "citation_keys": len(citations),
        "labels": len(labels),
        "headline_aggregates_checked": len(expected),
        "failures": failures,
        "note": "Static source/provenance audit only; a TeX engine is not installed on this host.",
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())

