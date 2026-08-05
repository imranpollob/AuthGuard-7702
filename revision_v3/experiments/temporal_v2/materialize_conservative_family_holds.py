"""Materialize anonymous, score-blind family-hold clusters for a frozen sample.

Brand attribution is preserved only where independently established.  All remaining items are
assigned to conservative must-link clusters and receive overinclusive similarity-based holds.
The resulting ``CONSERVATIVE_CLUSTER`` status is terminal for retraining but explicitly does
not claim project ownership or family independence.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
V3 = os.path.join(REPO_ROOT, "revision_v3")
sys.path.insert(0, os.path.join(V3, "src"))

from features.disassembler import linear_sweep, normalize_hex  # noqa: E402
from features.hashing import opcode_kgrams  # noqa: E402

CANONICAL = os.path.join(REPO_ROOT, "revision_v2", "data", "authguardbench_7702_v2.csv.gz")
CONTROL_REGISTRY = os.path.join(V3, "external_controls", "verified_legitimate_controls.csv")
CONTROL_CACHE = os.path.join(V3, "external_controls", "bytecode_cache")

MODERATE_SIMILARITY_HOLD = 0.50
WEAK_BEST_MATCH_FLOOR = 0.35
CONTROL_PROJECT_HOLD = 0.85
MAX_CANONICAL_HOLDS_PER_ITEM = 5
AUDITOR_ID = "CONSERVATIVE_LINKAGE_PIPELINE_V1"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _grams(runtime: str) -> set:
    tokens, _, _ = linear_sweep(normalize_hex(runtime))
    return opcode_kgrams(tokens, k=4)


def _jaccard(left: set, right: set) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _split(value: object) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    text = str(value).strip()
    if not text or text.upper() == "NONE":
        return set()
    return {part.strip() for part in text.replace(",", ";").split(";") if part.strip()}


def build_canonical_index() -> list[tuple[str, str, set]]:
    canonical = pd.read_csv(
        CANONICAL, usecols=["family_id", "bytecode_sha256", "runtime_bytecode"]
    ).sort_values(["family_id", "bytecode_sha256"])
    unique = canonical.drop_duplicates("bytecode_sha256", keep="first")
    return [
        (str(row.family_id), str(row.bytecode_sha256), _grams(str(row.runtime_bytecode)))
        for row in unique.itertuples(index=False)
    ]


def load_control_index() -> list[tuple[str, str, set]]:
    registry = pd.read_csv(CONTROL_REGISTRY)
    cache_paths = glob.glob(os.path.join(CONTROL_CACHE, "*.hex"))
    entries = []
    seen = set()
    for row in registry.to_dict("records"):
        address = str(row["address"]).lower().removeprefix("0x")
        path = next(
            (candidate for candidate in cache_paths if address in os.path.basename(candidate).lower()),
            None,
        )
        if path is None:
            continue
        with open(path) as handle:
            runtime = handle.read().strip()
        key = (str(row["project"]), hashlib.sha256(
            bytes.fromhex(runtime.lower().removeprefix("0x"))
        ).hexdigest())
        if key in seen:
            continue
        seen.add(key)
        entries.append((key[0], key[1], _grams(runtime)))
    if not entries:
        raise ValueError("no development legitimate-control runtimes were loaded")
    return sorted(entries, key=lambda value: (value[0], value[1]))


def similarity_holds(
    runtime: str,
    canonical_index: list[tuple[str, str, set]],
    control_index: list[tuple[str, str, set]],
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    grams = _grams(runtime)
    best_by_family: dict[str, float] = {}
    for family_id, _, reference in canonical_index:
        similarity = _jaccard(grams, reference)
        best_by_family[family_id] = max(best_by_family.get(family_id, -1.0), similarity)
    ranked = sorted(best_by_family.items(), key=lambda value: (-value[1], value[0]))
    canonical_holds = [
        value for value in ranked if value[1] >= MODERATE_SIMILARITY_HOLD
    ][:MAX_CANONICAL_HOLDS_PER_ITEM]
    if not canonical_holds and ranked and ranked[0][1] >= WEAK_BEST_MATCH_FLOOR:
        canonical_holds = [ranked[0]]

    best_by_project: dict[str, float] = {}
    for project, _, reference in control_index:
        similarity = _jaccard(grams, reference)
        best_by_project[project] = max(best_by_project.get(project, -1.0), similarity)
    control_holds = sorted(
        (
            (project, similarity)
            for project, similarity in best_by_project.items()
            if similarity >= CONTROL_PROJECT_HOLD
        ),
        key=lambda value: (-value[1], value[0]),
    )
    return canonical_holds, control_holds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--dependence", required=True)
    parser.add_argument("--existing-audit", required=True)
    parser.add_argument("--public-evidence", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--link-evidence", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for output in [args.output, args.link_evidence, args.report]:
        if os.path.exists(output) and not args.overwrite:
            raise FileExistsError(f"refusing to overwrite frozen output: {output}")

    manifest = pd.read_csv(args.manifest)
    dependence = pd.read_csv(args.dependence)
    existing = pd.read_csv(args.existing_audit, keep_default_na=False)
    public = pd.read_csv(args.public_evidence).fillna("")
    if manifest["item_id"].duplicated().any() or dependence["item_id"].duplicated().any():
        raise ValueError("manifest and dependence item IDs must be unique")
    expected = set(manifest["item_id"].astype(str))
    for name, frame in [("dependence", dependence), ("audit", existing), ("public", public)]:
        if set(frame["item_id"].astype(str)) != expected:
            raise ValueError(f"{name} population differs from the manifest")
    dependence_columns = [
        "item_id",
        "dependence_cluster_id",
        "dependence_cluster_size",
        "creator_address",
        "creator_kind",
        "linkage_evidence",
    ]
    merged = manifest.merge(
        dependence[dependence_columns], on="item_id", validate="one_to_one"
    ).merge(
        public[["item_id", "candidate_name_signals", "evidence_reference_candidates"]],
        on="item_id",
        validate="one_to_one",
    )
    existing_by_item = existing.set_index("item_id").to_dict("index")
    canonical_index = build_canonical_index()
    control_index = load_control_index()

    item_evidence = []
    item_holds: dict[str, dict] = {}
    for row in merged.sort_values("item_id").to_dict("records"):
        canonical_holds, control_holds = similarity_holds(
            str(row["runtime_bytecode"]), canonical_index, control_index
        )
        item_id = str(row["item_id"])
        item_holds[item_id] = {
            "canonical": {family for family, _ in canonical_holds},
            "controls": {project for project, _ in control_holds},
        }
        item_evidence.append({
            "item_id": item_id,
            "dependence_cluster_id": row["dependence_cluster_id"],
            "dependence_cluster_size": row["dependence_cluster_size"],
            "linkage_evidence": row["linkage_evidence"],
            "authority_address": row["authority_address"],
            "creator_address": row["creator_address"],
            "creator_kind": row["creator_kind"],
            "public_name_signals": row["candidate_name_signals"],
            "canonical_similarity_holds": ";".join(
                f"{family}:{similarity:.6f}" for family, similarity in canonical_holds
            ),
            "development_control_similarity_holds": ";".join(
                f"{project}:{similarity:.6f}" for project, similarity in control_holds
            ),
            "public_evidence_references": row["evidence_reference_candidates"],
        })

    evidence_path_relative = os.path.relpath(args.link_evidence, REPO_ROOT)
    audit_rows = []
    cluster_groups = merged.groupby("dependence_cluster_id", sort=True)
    for cluster_id, group in cluster_groups:
        item_ids = sorted(group["item_id"].astype(str))
        terminal = [
            existing_by_item[item_id]
            for item_id in item_ids
            if str(existing_by_item[item_id].get("provenance_status", "")).upper()
            in {"CONFIRMED", "EXCLUDED"}
        ]
        confirmed_ids = {
            str(record.get("postcutoff_project_family_id", "")).strip()
            for record in terminal
            if str(record.get("provenance_status", "")).upper() == "CONFIRMED"
        }
        confirmed_ids.discard("")
        if len(confirmed_ids) > 1:
            raise ValueError(f"conflicting confirmed projects inside {cluster_id}")
        if confirmed_ids:
            project_id = next(iter(confirmed_ids))
        else:
            digest = hashlib.sha256("\n".join(item_ids).encode()).hexdigest()[:12].upper()
            project_id = f"PF_ANON_{digest}"
        cluster_canonical = set().union(*(item_holds[item]["canonical"] for item in item_ids))
        cluster_controls = set().union(*(item_holds[item]["controls"] for item in item_ids))
        for item_id in item_ids:
            old = dict(existing_by_item[item_id])
            old["item_id"] = item_id
            old_status = str(old.get("provenance_status", "")).upper()
            if old_status == "EXCLUDED":
                audit_rows.append(old)
                continue
            manual_canonical = _split(old.get("related_canonical_family_ids"))
            manual_controls = _split(old.get("related_control_projects"))
            if old_status == "CONFIRMED":
                old["related_canonical_family_ids"] = ";".join(
                    sorted(cluster_canonical | manual_canonical)
                )
                old["related_control_projects"] = ";".join(
                    sorted(cluster_controls | manual_controls)
                )
                audit_rows.append(old)
                continue
            audit_rows.append({
                "item_id": item_id,
                "postcutoff_project_family_id": project_id,
                "provenance_status": "CONSERVATIVE_CLUSTER",
                "evidence_reference": f"artifact:{evidence_path_relative}#cluster={cluster_id}",
                "evidence_notes": (
                    "NO_BRAND_OWNERSHIP_CLAIM; score-blind must-link cluster with overinclusive "
                    "canonical and development-control similarity holds. Absence of a link does "
                    "not prove project independence."
                ),
                "related_canonical_family_ids": ";".join(sorted(cluster_canonical)),
                "related_control_projects": ";".join(sorted(cluster_controls)),
                "auditor_id": AUDITOR_ID,
                "exclusion_reason": "",
            })

    output = pd.DataFrame(audit_rows)[list(existing.columns)].sort_values(
        "item_id", kind="mergesort"
    )
    evidence = pd.DataFrame(item_evidence).sort_values("item_id", kind="mergesort")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    evidence.to_csv(args.link_evidence, index=False, lineterminator="\n")
    output.to_csv(args.output, index=False, lineterminator="\n")
    status_counts = output["provenance_status"].value_counts().sort_index().to_dict()
    all_holds = set()
    all_control_holds = set()
    for row in output.to_dict("records"):
        all_holds.update(_split(row["related_canonical_family_ids"]))
        all_control_holds.update(_split(row["related_control_projects"]))
    report = {
        "status": "SCORE_BLIND_CONSERVATIVE_FAMILY_HOLD_AUDIT_MATERIALIZED",
        "n_items": len(output),
        "n_linkage_clusters": int(dependence["dependence_cluster_id"].nunique()),
        "status_counts": {key: int(value) for key, value in status_counts.items()},
        "n_distinct_canonical_families_held": len(all_holds),
        "n_distinct_development_control_projects_held": len(all_control_holds),
        "similarity_hold_rules": {
            "moderate_canonical_threshold": MODERATE_SIMILARITY_HOLD,
            "weak_best_match_floor": WEAK_BEST_MATCH_FLOOR,
            "max_canonical_holds_per_item": MAX_CANONICAL_HOLDS_PER_ITEM,
            "development_control_threshold": CONTROL_PROJECT_HOLD,
        },
        "input_hashes": {
            os.path.relpath(path, REPO_ROOT): sha256_file(path)
            for path in [
                args.manifest,
                args.dependence,
                args.existing_audit,
                args.public_evidence,
                CANONICAL,
                CONTROL_REGISTRY,
            ]
        },
        "audit_sha256": sha256_file(args.output),
        "link_evidence_sha256": sha256_file(args.link_evidence),
        "builder_sha256": sha256_file(__file__),
        "claim_boundary": (
            "Anonymous clusters authorize conservative retraining holds only. They are not "
            "brand attribution, proof of project independence, or security labels."
        ),
    }
    with open(args.report, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
