"""Stage 2a: scan a configurable Ethereum block range and record every EIP-7702 authorization
entry (chain, block, tx hash, tx sender, full authorization tuple including y_parity/r/s).
No filtering by suspicion, labels, or predictions -- every type-0x4 authorization in range is
recorded. Resumable via checkpoint; re-running continues from the last scanned block.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dataset_pipeline")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from lib.config import load_config  # noqa: E402
from lib.collector import scan_block_range  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from temporal.rpc_client import ChainClient  # noqa: E402


def resolve_block_range(chain: str, range_cfg: dict) -> tuple[int, int]:
    if range_cfg.get("start_block") is not None and range_cfg.get("end_block") is not None:
        return range_cfg["start_block"], range_cfg["end_block"]
    client = ChainClient(chain)
    latest = client.block_number()
    end_block = latest
    start_block = max(0, latest - range_cfg["lookback_blocks"])
    return start_block, end_block


def main():
    cfg = load_config()
    out_dir = cfg["_resolved_paths"]["collected_delegates"]
    os.makedirs(out_dir, exist_ok=True)
    run_id = cfg["run_id"]
    manifest_path = os.path.join(out_dir, f"{run_id}_collection_manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

    for chain in cfg["chains"]:
        range_cfg = cfg["block_ranges"][chain]
        start_block, end_block = resolve_block_range(chain, range_cfg)
        print(f"[collect] {chain}: scanning blocks {start_block}..{end_block} "
              f"({end_block - start_block + 1} blocks)", flush=True)
        state = scan_block_range(
            chain, start_block, end_block, run_id, out_dir,
            sleep_between_blocks=cfg.get("sleep_between_blocks", 0.0),
        )
        manifest[chain] = {
            "requested_start_block": start_block,
            "requested_end_block": end_block,
            **state,
        }
        print(f"[collect] {chain}: done. {json.dumps(state, default=str)}", flush=True)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"[collect] manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
