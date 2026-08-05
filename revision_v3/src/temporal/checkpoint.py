"""Simple JSON checkpoint for resumable block scanning -- one file per chain, recording the
last successfully scanned block and accumulated counters. Safe to re-run: scanning restarts
from last_scanned_block + 1, never re-processes a completed block.
"""
from __future__ import annotations

import json
import os

CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "temporal", "checkpoints")


def checkpoint_path(chain: str, run_id: str) -> str:
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    return os.path.join(CHECKPOINT_DIR, f"{run_id}_{chain}.json")


def load_checkpoint(chain: str, run_id: str) -> dict:
    path = checkpoint_path(chain, run_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"chain": chain, "run_id": run_id, "last_scanned_block": None,
            "n_blocks_scanned": 0, "n_type4_txs": 0, "n_authorization_entries": 0,
            "n_rpc_errors": 0}


def save_checkpoint(chain: str, run_id: str, state: dict) -> None:
    with open(checkpoint_path(chain, run_id), "w") as f:
        json.dump(state, f, indent=2, default=str)
