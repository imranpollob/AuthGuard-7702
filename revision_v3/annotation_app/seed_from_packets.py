"""Seeds the annotation DB from a Phase 2 Part 7 sampling manifest CSV (columns: item_id,
sample_set, family_id, chain, address, runtime_bytecode) -- builds one evidence packet per
row (Part 5's builder, which structurally cannot see label/score columns) and creates the
initial reviewer assignments per sample-set rule:

  pilot:     both PRIMARY_PAIR reviewers assigned immediately.
  gold_dev:  PRIMARY_PAIR[0] assigned immediately; ~20% of items are pre-selected (seeded
             random) for a second review, recorded as an audit-log marker that
             assignment_rules.py checks after the first review is submitted.
  gold_test: both PRIMARY_PAIR reviewers assigned immediately; adjudicator assignment is
             fully dynamic (assignment_rules.py, triggered on disagreement).
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from db import db_session, init_db, log_action, now_iso  # noqa: E402
from evidence.packet_builder import build_evidence_packet  # noqa: E402
from features.selectors import build_sensitive_selector_set  # noqa: E402

PRIMARY_PAIR = os.environ.get("PRIMARY_REVIEWER_PAIR", "R1,R2").split(",")
GOLD_DEV_SECOND_REVIEW_FRACTION = 0.20
GOLD_DEV_PRESELECT_SEED = 770220261


def seed(manifest_path: str) -> None:
    init_db()
    sensitive_selectors = build_sensitive_selector_set()
    with open(manifest_path) as f:
        rows = list(csv.DictReader(f))

    gold_dev_ids = [r["item_id"] for r in rows if r["sample_set"] == "gold_dev"]
    rng = random.Random(GOLD_DEV_PRESELECT_SEED)
    n_preselect = max(1, int(round(len(gold_dev_ids) * GOLD_DEV_SECOND_REVIEW_FRACTION)))
    preselected = set(rng.sample(gold_dev_ids, n_preselect)) if gold_dev_ids else set()

    with db_session() as conn:
        for reviewer_id in set(PRIMARY_PAIR):
            conn.execute(
                "INSERT INTO reviewers (reviewer_id, display_name, role, created_at) VALUES (?, ?, 'primary', ?) "
                "ON CONFLICT(reviewer_id) DO NOTHING", (reviewer_id, reviewer_id, now_iso()),
            )

        for row in rows:
            safe_row = {
                "sample_id": row["item_id"], "chain": row["chain"], "address": row["address"],
                "runtime_bytecode": row["runtime_bytecode"],
            }
            packet = build_evidence_packet(safe_row, sensitive_selectors=sensitive_selectors)
            conn.execute(
                "INSERT INTO items (item_id, sample_set, evidence_json, family_id, created_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(item_id) DO NOTHING",
                (row["item_id"], row["sample_set"], json.dumps(packet), row.get("family_id"), now_iso()),
            )

            reviewers_to_assign = list(PRIMARY_PAIR) if row["sample_set"] in ("pilot", "gold_test") else [PRIMARY_PAIR[0]]
            for reviewer_id in reviewers_to_assign:
                conn.execute(
                    "INSERT OR IGNORE INTO assignments (item_id, reviewer_id, is_adjudication, status, assigned_at) "
                    "VALUES (?, ?, 0, 'pending', ?)", (row["item_id"], reviewer_id, now_iso()),
                )

            if row["item_id"] in preselected:
                log_action(conn, "system", "gold_dev_second_review_preselected", row["item_id"])

        log_action(conn, "system", "seed_from_packets", detail={
            "manifest": manifest_path, "n_items": len(rows), "n_gold_dev_preselected": len(preselected),
        })

    print(f"seeded {len(rows)} items from {manifest_path} "
          f"({len(preselected)} gold_dev items pre-selected for second review)")


if __name__ == "__main__":
    seed(sys.argv[1])
