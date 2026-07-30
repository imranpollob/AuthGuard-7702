"""Exportable release schema: one finalized row per item, applying the adjudication rule
(if two primary reviewers agree, that label is final; if they disagree, the adjudicator's
label is final; if only one primary review exists and no adjudication was required, that
single review is final -- e.g. Gold-Dev's 20% second-review sample)."""
from __future__ import annotations

import csv
import json
import os
import sys

from db import get_connection


def finalize_item(item_id: str, conn) -> dict | None:
    rows = conn.execute(
        "SELECT reviewer_id, label, unsafe_category, indeterminate_reason, confidence, rationale, "
        "evidence_consulted, is_adjudication, created_at FROM annotations "
        "WHERE item_id = ? AND is_draft = 0", (item_id,),
    ).fetchall()
    if not rows:
        return None
    primary = [r for r in rows if not r["is_adjudication"]]
    adjudication = next((r for r in rows if r["is_adjudication"]), None)

    if adjudication is not None:
        final = adjudication
        resolution = "adjudicated"
    elif len(primary) >= 2:
        labels = {r["label"] for r in primary}
        if len(labels) == 1:
            final = primary[0]
            resolution = "unanimous"
        else:
            return {
                "item_id": item_id, "resolution": "UNRESOLVED_DISAGREEMENT_NO_ADJUDICATION",
                "n_primary_reviews": len(primary), "final_label": None,
            }
    elif len(primary) == 1:
        final = primary[0]
        resolution = "single_review"
    else:
        return None

    return {
        "item_id": item_id,
        "resolution": resolution,
        "n_primary_reviews": len(primary),
        "final_label": final["label"],
        "final_unsafe_category": final["unsafe_category"],
        "final_indeterminate_reason": final["indeterminate_reason"],
        "final_confidence": final["confidence"],
        "final_rationale": final["rationale"],
        "final_evidence_consulted": final["evidence_consulted"],
        "finalized_by": "adjudicator" if adjudication is not None else "primary_reviewer",
    }


def export_release(sample_set: str | None = None) -> list[dict]:
    conn = get_connection()
    query = "SELECT item_id, sample_set FROM items"
    params = ()
    if sample_set:
        query += " WHERE sample_set = ?"
        params = (sample_set,)
    items = conn.execute(query, params).fetchall()

    rows = []
    for item in items:
        finalized = finalize_item(item["item_id"], conn)
        if finalized is not None:
            finalized["sample_set"] = item["sample_set"]
            rows.append(finalized)
    conn.close()
    return rows


def main():
    sample_set = sys.argv[1] if len(sys.argv) > 1 else None
    rows = export_release(sample_set)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    suffix = f"_{sample_set}" if sample_set else "_all"
    json_path = os.path.join(out_dir, f"release{suffix}.json")
    csv_path = os.path.join(out_dir, f"release{suffix}.csv")
    with open(json_path, "w") as f:
        json.dump(rows, f, indent=2)
    if rows:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r.keys()}))
            writer.writeheader()
            writer.writerows(rows)
    print(f"exported {len(rows)} finalized rows -> {json_path}")


if __name__ == "__main__":
    main()
