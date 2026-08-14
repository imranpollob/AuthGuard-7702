#!/usr/bin/env python3
"""RQ4 parameter-matched experiment restricted to the Tier-B action space.

This is an isolated entry point. It does not modify the shared attack implementation, the
runner, the architectures, the training procedure, or the statistics. It imports the
existing runner and restricts the sampleable action space in place before delegating to
the runner's own main(), so every other constraint continues to be enforced by the same
code that produced the full-action replication.

Tier B = the transformation classes with independent execution-preservation support:
  metadata rewrite, neutral instruction insertion, flooding at 25/50/100/200%.
Excluded: address rewriting and selector rewriting (weaker preservation evidence).

The restriction is applied to the `search` module's ACTIONS global, which is what
random_sequences() and beam_search() read. FLOOD_ACTIONS is left untouched, so the
"at most one flooding action" rule, the depth limit, the query budget, the byte budget,
donor isolation, thresholds, and the success definition are all unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
RUNNER = os.path.join(RV2, "experiments", "adaptive_attacks_v2",
                      "run_adaptive_attacks_v2.py")

TIER_B_ACTIONS = ("metadata", "neutral25",
                  "flood25", "flood50", "flood100", "flood200")
EXCLUDED = ("address", "selector")


def load_runner():
    spec = importlib.util.spec_from_file_location("run_adaptive_attacks_v2", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_adaptive_attacks_v2"] = module
    spec.loader.exec_module(module)
    return module


def restrict(runner):
    """Patch the search module's ACTIONS in place and return an audit record."""
    search = sys.modules["search"]          # the instance the runner imported from
    before = tuple(search.ACTIONS)
    search.ACTIONS = TIER_B_ACTIONS
    runner.ACTIONS = TIER_B_ACTIONS         # keep the runner's re-export consistent
    return dict(actions_before=list(before),
                actions_after=list(search.ACTIONS),
                excluded=list(EXCLUDED),
                flood_actions_unchanged=sorted(search.FLOOD_ACTIONS))


def validate(runner, budget, audit):
    """Step 1 checks: prove the restriction holds and nothing else moved."""
    search = sys.modules["search"]
    checks = []

    def ck(name, ok, detail=""):
        checks.append(dict(check=name, passed=bool(ok), detail=str(detail)))

    ck("action list is exactly Tier B", tuple(search.ACTIONS) == TIER_B_ACTIONS,
       list(search.ACTIONS))
    ck("address excluded", "address" not in search.ACTIONS)
    ck("selector excluded", "selector" not in search.ACTIONS)

    # random search: exhaustively enumerate the sequences it can emit
    seqs = search.random_sequences("audit-probe", budget, runner.MAX_DEPTH)
    emitted = {a for s in seqs for a in s}
    ck("random search cannot sample address/selector",
       not (emitted & set(EXCLUDED)), sorted(emitted))
    ck("random search respects max depth",
       all(len(s) <= runner.MAX_DEPTH for s in seqs),
       max((len(s) for s in seqs), default=0))
    ck("random search respects one-flooding rule",
       all(sum(a in search.FLOOD_ACTIONS for a in s) <= 1 for s in seqs))

    # beam search expands over ACTIONS directly; verify the same closure
    reachable = set()
    frontier = [()]
    for _ in range(runner.MAX_DEPTH):
        nxt = []
        for seq in frontier:
            for a in search.ACTIONS:
                if search.sequence_allowed(seq, a):
                    nxt.append(seq + (a,))
                    reachable.add(a)
        frontier = nxt[:200]
    ck("beam search cannot expand address/selector",
       not (reachable & set(EXCLUDED)), sorted(reachable))

    ck("query budget is 64", runner.QUERY_BUDGET == 64, runner.QUERY_BUDGET)
    ck("beam width is 4", runner.BEAM_WIDTH == 4, runner.BEAM_WIDTH)
    ck("max depth is 4", runner.MAX_DEPTH == 4, runner.MAX_DEPTH)
    ck("byte overhead cap is 2.0", runner.MAX_OVERHEAD == 2.0, runner.MAX_OVERHEAD)
    ck("flood levels unchanged",
       sorted(search.FLOOD_ACTIONS) == ["flood100", "flood200", "flood25", "flood50"],
       sorted(search.FLOOD_ACTIONS))
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    runner = load_runner()
    audit = restrict(runner)
    checks = validate(runner, args.budget, audit)

    print("=== Tier-B action-space restriction ===")
    print(f"  before : {audit['actions_before']}")
    print(f"  after  : {audit['actions_after']}")
    print(f"  excluded: {audit['excluded']}")
    for c in checks:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check']}"
              f"{('  ' + c['detail']) if (c['detail'] and not c['passed']) else ''}")
    if not all(c["passed"] for c in checks):
        raise SystemExit("Tier-B restriction validation FAILED; not running")

    out_dir = os.path.join(RV2, "results", "rq4_replication_3seed_tierb")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"tierb_action_audit_s{args.seed}.json"), "w") as fh:
        json.dump(dict(seed=args.seed, audit=audit, checks=checks,
                       query_budget=args.budget, beam_width=runner.BEAM_WIDTH,
                       max_depth=runner.MAX_DEPTH,
                       max_byte_overhead=runner.MAX_OVERHEAD), fh, indent=2)
    if args.validate_only:
        print("[tierb] validate-only: not running the attack")
        return 0

    # Seed-bearing tag so no seed's output can overwrite another's.
    tag = f"tierb_s{args.seed}"
    sys.argv = ["run_adaptive_attacks_v2.py",
                "--seed", str(args.seed),
                "--folds", *[str(f) for f in args.folds],
                "--budget", str(args.budget),
                "--epochs", str(args.epochs),
                "--models", "chunk_attention_16384", "chunk_mean_16384",
                "flat_control_16384",
                "--tag", tag]
    print(f"[tierb] delegating to runner with tag={tag}", flush=True)
    return runner.main()


if __name__ == "__main__":
    sys.exit(main())
