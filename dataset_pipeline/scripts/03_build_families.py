"""Stage 3: group the collected population by (1) exact runtime-bytecode hash and (2)
opcode-based similarity (exact Jaccard over opcode 4-grams, union-find at threshold 0.85).
Assigns exact_bytecode_id and bytecode_family_id to every screenable delegate.
NOTSCREENABLE delegates (no bytecode) get null ids and are kept in the output, not dropped.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.families import (  # noqa: E402
    FAMILY_SIMILARITY_THRESHOLD, cluster_by_similarity, opcode_grams_for_bytecode, relabel,
)


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    pop_dir = cfg["_resolved_paths"]["collected_delegates"]
    out_dir = cfg["_resolved_paths"]["bytecode_families"]
    os.makedirs(out_dir, exist_ok=True)

    frames = []
    for chain in cfg["chains"]:
        pop_path = os.path.join(pop_dir, f"{run_id}_{chain}_population.csv")
        if not os.path.exists(pop_path):
            continue
        frames.append(pd.read_csv(pop_path))
    population = pd.concat(frames, ignore_index=True)

    screenable = population[population["retrieval_status"] == "OK"].copy().reset_index(drop=True)
    notscreenable = population[population["retrieval_status"] != "OK"].copy().reset_index(drop=True)

    # 1. Exact bytecode grouping
    exact_order = {}
    exact_ids = []
    for h in screenable["bytecode_sha256"]:
        if h not in exact_order:
            exact_order[h] = len(exact_order) + 1
        exact_ids.append(f"EXACT{exact_order[h]:05d}")
    screenable["exact_bytecode_id"] = exact_ids

    # 2. Opcode-similarity family grouping over one representative bytecode per exact id
    #    (identical bytecodes are trivially >=threshold-similar to each other, so clustering
    #    representatives and then propagating is equivalent to clustering everyone and cheaper).
    reps = screenable.drop_duplicates("exact_bytecode_id").sort_values("exact_bytecode_id")
    gram_sets = [opcode_grams_for_bytecode(bc) for bc in reps["runtime_bytecode"]]
    roots = cluster_by_similarity(gram_sets, threshold=FAMILY_SIMILARITY_THRESHOLD)
    rep_family_ids = relabel(roots, prefix="FAM")
    exact_to_family = dict(zip(reps["exact_bytecode_id"], rep_family_ids))
    screenable["bytecode_family_id"] = screenable["exact_bytecode_id"].map(exact_to_family)

    notscreenable["exact_bytecode_id"] = None
    notscreenable["bytecode_family_id"] = None

    out = pd.concat([screenable, notscreenable], ignore_index=True)
    family_size = screenable.groupby("bytecode_family_id").size().rename("family_size")
    out = out.merge(family_size, left_on="bytecode_family_id", right_index=True, how="left")

    out_path = os.path.join(out_dir, f"{run_id}_family_assignment.csv")
    out.to_csv(out_path, index=False)

    n_families = screenable["bytecode_family_id"].nunique()
    n_exact = screenable["exact_bytecode_id"].nunique()
    singletons = int((family_size == 1).sum())
    summary = {
        "n_screenable": int(len(screenable)),
        "n_notscreenable": int(len(notscreenable)),
        "n_exact_bytecode_groups": int(n_exact),
        "n_bytecode_families": int(n_families),
        "singleton_families": singletons,
        "singleton_pct": round(100 * singletons / n_families, 1) if n_families else None,
        "largest_family_size": int(family_size.max()) if n_families else None,
        "similarity_threshold": FAMILY_SIMILARITY_THRESHOLD,
        "output_csv": out_path,
    }
    print(json.dumps(summary, indent=2))
    with open(os.path.join(out_dir, f"{run_id}_family_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
