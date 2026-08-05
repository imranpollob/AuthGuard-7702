"""Seeds the annotation DB from a Phase 2 Part 7 sampling manifest CSV (columns: item_id,
sample_set, family_id, chain, address, runtime_bytecode) -- builds one evidence packet per
row (Part 5's builder, which structurally cannot see label/score columns) and creates the
initial reviewer assignments per sample-set rule:

  pilot:     both PRIMARY_PAIR reviewers assigned immediately.
  gold_dev:  PRIMARY_PAIR[0] assigned immediately; ~20% of items are pre-selected (seeded
             random) for a second review, recorded as an audit-log marker that
             assignment_rules.py checks after the first review is submitted.
  gold_test/postcutoff: both PRIMARY_PAIR reviewers assigned immediately; adjudicator
             assignment is fully dynamic (assignment_rules.py, triggered on disagreement).
"""
from __future__ import annotations

import csv
import hashlib
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


def _validate_primary_pair(reviewers: list[str]) -> list[str]:
    normalized = [value.strip() for value in reviewers if value.strip()]
    if len(normalized) != 2 or len(set(normalized)) != 2:
        raise ValueError(
            "PRIMARY_REVIEWER_PAIR must contain exactly two distinct reviewer IDs"
        )
    return normalized


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed(manifest_path: str) -> None:
    primary_pair = _validate_primary_pair(PRIMARY_PAIR)
    init_db()
    sensitive_selectors = build_sensitive_selector_set()
    with open(manifest_path) as f:
        rows = list(csv.DictReader(f))
    item_ids = [row.get("item_id") for row in rows]
    if not rows or any(not value for value in item_ids) or len(set(item_ids)) != len(item_ids):
        raise ValueError("annotation manifest must contain nonempty unique item_id values")

    gold_dev_ids = [r["item_id"] for r in rows if r["sample_set"] == "gold_dev"]
    rng = random.Random(GOLD_DEV_PRESELECT_SEED)
    n_preselect = max(1, int(round(len(gold_dev_ids) * GOLD_DEV_SECOND_REVIEW_FRACTION)))
    preselected = set(rng.sample(gold_dev_ids, n_preselect)) if gold_dev_ids else set()

    with db_session() as conn:
        for reviewer_id in primary_pair:
            conn.execute(
                "INSERT INTO reviewers (reviewer_id, display_name, role, created_at) VALUES (?, ?, 'primary', ?) "
                "ON CONFLICT(reviewer_id) DO NOTHING", (reviewer_id, reviewer_id, now_iso()),
            )

        for row in rows:
            safe_row = {
                "sample_id": row["item_id"], "chain": row["chain"], "address": row["address"],
                "runtime_bytecode": row["runtime_bytecode"],
            }
            if row["sample_set"] == "postcutoff":
                safe_row.update({
                    key: row.get(key) for key in (
                        "authority_address", "authorization_count", "first_block",
                        "first_tx_hash", "runtime_changed_since_first_authorization",
                    )
                })
            packet = build_evidence_packet(safe_row, sensitive_selectors=sensitive_selectors)
            expected_hash = (row.get("bytecode_sha256") or "").lower().removeprefix("0x")
            if expected_hash and expected_hash != packet["runtime_bytecode_sha256"]:
                raise ValueError(
                    f"{row['item_id']}: manifest bytecode hash does not match runtime"
                )
            packet_json = json.dumps(packet, sort_keys=True)
            existing_item = conn.execute(
                "SELECT sample_set, evidence_json FROM items WHERE item_id = ?", (row["item_id"],)
            ).fetchone()
            if existing_item is None:
                conn.execute(
                    "INSERT INTO items (item_id, sample_set, evidence_json, family_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (row["item_id"], row["sample_set"], packet_json,
                     row.get("family_id"), now_iso()),
                )
            else:
                if existing_item["sample_set"] != row["sample_set"]:
                    raise ValueError(
                        f"{row['item_id']}: existing item belongs to sample set "
                        f"{existing_item['sample_set']!r}, not {row['sample_set']!r}"
                    )
                n_annotations = conn.execute(
                    "SELECT COUNT(*) FROM annotations WHERE item_id = ?", (row["item_id"],)
                ).fetchone()[0]
                if existing_item["evidence_json"] != packet_json:
                    if n_annotations:
                        raise ValueError(
                            f"{row['item_id']}: refusing to change evidence after annotation began"
                        )
                    conn.execute(
                        "UPDATE items SET evidence_json = ?, family_id = ? WHERE item_id = ?",
                        (packet_json, row.get("family_id"), row["item_id"]),
                    )
                    log_action(conn, "system", "evidence_packet_refreshed", row["item_id"])

            reviewers_to_assign = (
                list(primary_pair)
                if row["sample_set"] in ("pilot", "gold_test", "postcutoff")
                else [primary_pair[0]]
            )
            for reviewer_id in reviewers_to_assign:
                conn.execute(
                    "INSERT OR IGNORE INTO assignments (item_id, reviewer_id, is_adjudication, status, assigned_at) "
                    "VALUES (?, ?, 0, 'pending', ?)", (row["item_id"], reviewer_id, now_iso()),
                )

            if row["item_id"] in preselected:
                log_action(conn, "system", "gold_dev_second_review_preselected", row["item_id"])

        log_action(conn, "system", "seed_from_packets", detail={
            "manifest": manifest_path,
            "manifest_sha256": _sha256_file(manifest_path),
            "n_items": len(rows),
            "n_gold_dev_preselected": len(preselected),
        })

    print(f"seeded {len(rows)} items from {manifest_path} "
          f"({len(preselected)} gold_dev items pre-selected for second review)")


if __name__ == "__main__":
    seed(sys.argv[1])
