#!/usr/bin/env python3
"""Static source and numerical-provenance audit for the v3 final manuscript."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
RV2 = HERE.parent
RESULTS = RV2 / "results"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def one(items: list[dict[str, str]], **query: str) -> dict[str, str]:
    matches = [
        row for row in items
        if all(row.get(key) == value for key, value in query.items())
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one row for {query}, found {len(matches)}")
    return matches[0]


def close(actual: str | float, expected: float, tolerance: float = 5e-7) -> bool:
    return abs(float(actual) - expected) <= tolerance


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    main_path = HERE / "main_final.tex"
    main_text = main_path.read_text(encoding="utf-8")
    combined = main_text

    for item in re.findall(r"\\input\{([^}]+)\}", main_text):
        path = HERE / (item if item.endswith(".tex") else f"{item}.tex")
        if not path.exists():
            failures.append(f"missing input: {item}")
        else:
            combined += "\n" + path.read_text(encoding="utf-8")

    for item in re.findall(
        r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", main_text
    ):
        if not (HERE / item).exists():
            failures.append(f"missing graphic: {item}")

    # Bounded syntax checks that do not require a TeX installation.
    code = "\n".join(
        re.split(r"(?<!\\)%", line, maxsplit=1)[0]
        for line in combined.splitlines()
    )
    code = code.replace(r"\{", "").replace(r"\}", "")
    balance = minimum = 0
    for char in code:
        if char == "{":
            balance += 1
        elif char == "}":
            balance -= 1
            minimum = min(minimum, balance)
    if balance or minimum < 0:
        failures.append(f"unbalanced braces: final={balance}, minimum={minimum}")

    begins = re.findall(r"\\begin\{([^}]+)\}", combined)
    ends = re.findall(r"\\end\{([^}]+)\}", combined)
    if sorted(begins) != sorted(ends):
        failures.append("LaTeX begin/end environment counts differ")

    labels = re.findall(r"\\label\{([^}]+)\}", combined)
    refs = re.findall(r"\\(?:ref|eqref)\{([^}]+)\}", combined)
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        failures.append(f"duplicate labels: {duplicates}")
    missing_refs = sorted(set(refs) - set(labels))
    if missing_refs:
        failures.append(f"undefined references: {missing_refs}")

    citations: set[str] = set()
    for group in re.findall(r"\\cite\{([^}]+)\}", combined):
        citations.update(key.strip() for key in group.split(","))
    bibitems = set(re.findall(r"\\bibitem\{([^}]+)\}", combined))
    if citations - bibitems:
        failures.append(f"undefined citations: {sorted(citations - bibitems)}")

    forbidden = (
        "181,877-parameter hierarchical architecture",
        "ranking first among seven",
        "outperforms six traditional",
        "retains 0.920 auprc",
        "median latency of 4.121",
        "742,625 bytes",
        "m3f200",
        "rewrite+flood",
    )
    lowered = main_text.lower()
    for phrase in forbidden:
        if phrase in lowered:
            failures.append(f"stale or forbidden claim: {phrase}")

    required = (
        "30,050-parameter hierarchical opcode model",
        "cap-correct Flood-200",
        "Flat-16K is strongest on clean ranking",
        "temporal generalization remains untested",
        "do not claim a runtime advantage",
        "125,300-byte checkpoint",
        "2.942 ms median",
    )
    for phrase in required:
        if phrase not in main_text:
            failures.append(f"required evidence boundary missing: {phrase}")

    try:
        summary = rows(RESULTS / "long_context_ablation_v3" / "summary.csv")
        checks = (
            (one(summary, model="chunk_attention_control_16384", condition="M0"),
             "AUPRC_mean", 0.917570),
            (one(summary, model="flat_control_16384", condition="M0"),
             "AUPRC_mean", 0.935716),
            (one(summary, model="chunk_attention_control_16384", condition="F200"),
             "AUPRC_mean", 0.907996),
            (one(summary, model="flat_control_16384", condition="F200"),
             "AUPRC_mean", 0.810037),
        )
        for row, field, expected in checks:
            if not close(row[field], expected, tolerance=5e-6):
                failures.append(
                    f"aggregate mismatch {row['model']}/{row['condition']}/{field}"
                )

        contrasts = rows(
            RESULTS / "long_context_ablation_v3" / "fold_clustered_contrasts.csv"
        )
        hierarchy = one(
            contrasts, contrast="hierarchy", condition="F200", metric="AUPRC"
        )
        attention = one(
            contrasts, contrast="attention", condition="M0", metric="AUPRC"
        )
        for row, targets in (
            (hierarchy, (0.097959, 0.059045, 0.154374)),
            (attention, (0.038583, 0.007232, 0.064256)),
        ):
            for field, expected in zip(
                ("delta", "ci95_low", "ci95_high"), targets, strict=True
            ):
                if not close(row[field], expected, tolerance=5e-6):
                    failures.append(
                        f"contrast mismatch {row['contrast']}/{row['condition']}/{field}"
                    )

        external = one(
            rows(
                RESULTS
                / "long_context_ablation_v3"
                / "operational_controls"
                / "external_summary.csv"
            ),
            model="chunk_attention_control_16384",
        )
        if not close(external["FPR_05_mean"], 0.0592221):
            failures.append("external nominal-5%-FPR aggregate mismatch")

        runtime = json.loads(
            (
                RESULTS
                / "long_context_ablation_v3"
                / "operational_controls"
                / "runtime.json"
            ).read_text(encoding="utf-8")
        )
        if runtime["trainable_params"] != 30050:
            failures.append("runtime model parameter count mismatch")
        if runtime["checkpoint_bytes"] != 125300:
            failures.append("runtime checkpoint byte count mismatch")
        if not close(runtime["complete_local_path"]["median_ms"], 2.942382):
            failures.append("complete-path median mismatch")

        confirmation = one(
            rows(RESULTS / "multiscale_confirmation_v1" / "summary.csv"),
            model="authguard_msp_16384",
            condition="M0",
        )
        if not close(confirmation["AUPRC_mean"], 0.948852, tolerance=5e-6):
            failures.append("confirmatory clean AUPRC mismatch")
    except (FileNotFoundError, KeyError, ValueError) as exc:
        failures.append(f"numerical provenance audit could not complete: {exc}")

    if "\\author{" not in main_text:
        warnings.append(
            "author block is intentionally absent; add the submission-specific "
            "anonymous or camera-ready author block before release"
        )
    warnings.append(
        "static source/provenance audit only; confirm that AuthGuard_7702_v3.pdf "
        "was rebuilt after the latest source change"
    )

    payload = {
        "pass": not failures,
        "tex_files_checked": 1 + len(re.findall(r"\\input\{([^}]+)\}", main_text)),
        "graphics_checked": len(
            re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", main_text)
        ),
        "citation_keys": len(citations),
        "labels": len(labels),
        "failures": failures,
        "warnings": warnings,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
