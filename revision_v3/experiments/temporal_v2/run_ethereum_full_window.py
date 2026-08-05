"""Part 11: launches the real, checkpointed Ethereum temporal collection toward the target
window 2026-02-01 through 2026-06-30. This is resumable (safe to kill and re-run; it picks
up from revision_v3/temporal/checkpoints/ethereum_v2.json) and is expected to take far longer
than one interactive session at the measured real throughput from the Phase 2 pilot
(~6.9 blocks/sec single-threaded on eth.drpc.org, no batching -- see
revision_v3/temporal/checkpoints/pilot_v1_ethereum.json). It is launched here as a real
background process; TEMPORAL_COLLECTION_FINAL_STATUS.md reports the actual block range
covered by the time this pipeline pass concludes, not a projected/assumed completion.

Usage:
    python3 revision_v3/experiments/temporal_v2/run_ethereum_full_window.py
"""
from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))

from temporal.collector import scan_block_range  # noqa: E402
from temporal.rpc_client import ChainClient  # noqa: E402

RUN_ID = "v2_window"
CHAIN = "ethereum"
WINDOW_START_UNIX = 1769904000  # 2026-02-01T00:00:00Z
WINDOW_END_UNIX = 1782777600    # 2026-06-30T00:00:00Z


def main() -> int:
    client = ChainClient(CHAIN)
    print("[temporal_v2] resolving block range for target window via binary search...", flush=True)
    start_block = client.find_block_by_timestamp(WINDOW_START_UNIX)
    end_block = client.find_block_by_timestamp(WINDOW_END_UNIX)
    print(f"[temporal_v2] {CHAIN}: window 2026-02-01..2026-06-30 -> blocks [{start_block}, {end_block}] "
          f"({end_block - start_block + 1} blocks)", flush=True)

    manifest_path = os.path.join(REPO_ROOT, "revision_v3", "temporal", "checkpoints", f"{RUN_ID}_{CHAIN}_range.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump({"chain": CHAIN, "run_id": RUN_ID, "window_start_unix": WINDOW_START_UNIX,
                   "window_end_unix": WINDOW_END_UNIX, "start_block": start_block,
                   "end_block": end_block, "n_blocks_total": end_block - start_block + 1}, f, indent=2)

    print("[temporal_v2] starting checkpointed scan (resumable)...", flush=True)
    state = scan_block_range(CHAIN, start_block, end_block, RUN_ID, fetch_bytecode=True)
    print(f"[temporal_v2] stopped/finished. state={state}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
