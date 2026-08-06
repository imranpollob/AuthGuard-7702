"""Stage 7.1: validate the completed human review file and freeze an immutable copy.

Checks every row rather than sampling: valid decision, valid final label/confidence, and -- for
ACCEPT_LLM_LABEL rows -- that final_label actually equals llm_label. Any malformed row is
rejected by review_id with a reason; the frozen copy is only written when zero rejections remain.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402

VALID_DECISIONS = {"ACCEPT_LLM_LABEL", "CHANGE_LABEL", "UNRESOLVED"}
VALID_LABELS = {"R1", "R2", "B", "U"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    hr_dir = cfg["_resolved_paths"]["human_reviews"]
    source = os.path.join(hr_dir, f"{run_id}_representative_gold_queue_promptv3.csv")
    df = pd.read_csv(source, keep_default_na=False)

    rejected = []
    accepted, changed, unresolved = 0, 0, 0
    for r in df.to_dict("records"):
        rid = r.get("review_id", "<missing review_id>")
        decision = str(r.get("decision", "")).strip()
        final_label = str(r.get("final_label", "")).strip()
        final_conf = str(r.get("final_confidence", "")).strip()
        llm_label = str(r.get("llm_label", "")).strip()

        if decision not in VALID_DECISIONS:
            rejected.append({"review_id": rid, "reason": f"invalid/missing decision {decision!r}"})
            continue
        if final_conf and final_conf not in VALID_CONFIDENCE:
            rejected.append({"review_id": rid, "reason": f"invalid final_confidence {final_conf!r}"})
            continue
        if decision == "ACCEPT_LLM_LABEL":
            if llm_label not in VALID_LABELS:
                rejected.append({"review_id": rid, "reason": f"invalid llm_label {llm_label!r}"})
                continue
            if final_label and final_label != llm_label:
                rejected.append({"review_id": rid,
                                 "reason": f"ACCEPT_LLM_LABEL but final_label {final_label!r} != llm_label {llm_label!r}"})
                continue
            accepted += 1
        elif decision == "CHANGE_LABEL":
            if final_label not in VALID_LABELS:
                rejected.append({"review_id": rid, "reason": f"CHANGE_LABEL needs valid final_label, got {final_label!r}"})
                continue
            if final_conf not in VALID_CONFIDENCE:
                rejected.append({"review_id": rid, "reason": "CHANGE_LABEL needs final_confidence"})
                continue
            changed += 1
        else:
            unresolved += 1

    if df["review_id"].duplicated().any():
        dupes = df.loc[df["review_id"].duplicated(keep=False), "review_id"].unique().tolist()
        rejected.append({"review_id": ",".join(map(str, dupes[:10])), "reason": "duplicate review_id"})

    summary = {
        "source_file": source,
        "n_rows": int(len(df)),
        "n_reviewed": accepted + changed + unresolved,
        "n_accepted_llm_label": accepted,
        "n_changed_label": changed,
        "n_unresolved": unresolved,
        "n_rejected": len(rejected),
        "rejections": rejected[:20],
        "final_label_distribution": df["final_label"].replace("", pd.NA).fillna(df["llm_label"]).value_counts().to_dict(),
        "final_confidence_distribution": df["final_confidence"].value_counts().to_dict(),
    }

    if rejected:
        print(json.dumps(summary, indent=2, default=str))
        raise SystemExit(f"REFUSING to freeze: {len(rejected)} malformed row(s)")

    frozen_dir = os.path.join(hr_dir, "frozen")
    os.makedirs(frozen_dir, exist_ok=True)
    frozen_path = os.path.join(frozen_dir, f"{run_id}_gold_review_FROZEN.csv")
    shutil.copy2(source, frozen_path)
    os.chmod(frozen_path, 0o444)  # read-only: this is the immutable record

    digest = sha256_file(frozen_path)
    summary["frozen_copy"] = frozen_path
    summary["frozen_sha256"] = digest
    summary["source_sha256"] = sha256_file(source)

    with open(os.path.join(frozen_dir, f"{run_id}_gold_review_FROZEN.sha256"), "w") as f:
        f.write(f"{digest}  {os.path.basename(frozen_path)}\n")
    with open(os.path.join(frozen_dir, f"{run_id}_gold_review_validation.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))
    print(f"\n{summary['n_reviewed']} reviewed, {accepted} accepted, {changed} changed, "
          f"{unresolved} unresolved, {len(rejected)} rejected")


if __name__ == "__main__":
    main()
