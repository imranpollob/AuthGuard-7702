#!/usr/bin/env bash
# Regenerates every sprint analysis from the frozen checkpoints and stored artifacts.
#
# Phases 0 and 1 read the historical attack records and need no models.
# Phase 2 needs foundry/anvil on PATH.
# Phase 3 is the only step that trains; it is required once, before Phases 4 and 5.
# Phases 4 and 5 load the Phase 3 checkpoints and never retrain.
#
# Usage:  bash revision_v2/experiments/sprint_phase6/run_all_sprint.sh [--with-training]
set -euo pipefail

cd "$(dirname "$0")/../../.."
export PATH="$HOME/.foundry/bin:$PATH"
E=revision_v2/experiments
WITH_TRAINING="${1:-}"

echo "== frozen-artifact guard =="
python3 $E/common/frozen.py verify

echo "== Phase 0: restricted fixed oracles from stored scores =="
python3 $E/sprint_phase0/phase0_fixed_oracles.py
python3 $E/sprint_phase0/phase0_paired_ladder.py
python3 $E/sprint_phase0/phase0_winner_composition.py

echo "== Phase 1: seed scope and factual repairs =="
python3 $E/sprint_phase1/phase1_seed_scope.py
python3 $E/sprint_phase1/phase1_facts.py

echo "== Phase 2: expanded execution-preservation audit (needs anvil) =="
python3 $E/sprint_phase2/expanded_preservation_audit.py --n-delegates 120

if [ "$WITH_TRAINING" = "--with-training" ]; then
  echo "== Phase 3: regenerate and freeze checkpoints (TRAINS) =="
  python3 $E/sprint_phase3/regenerate_checkpoints.py --seed 7702 --folds 0 1 2 3 4 --epochs 30
else
  echo "== Phase 3 skipped; using existing checkpoints in results/sprint_phase3/checkpoints =="
  test -d revision_v2/results/sprint_phase3/checkpoints
fi

echo "== Phase 4: tiered attack against frozen checkpoints =="
python3 $E/sprint_phase4/run_tiered_attack.py --seed 7702 --folds 0 1 2 3 4 --budget 64 --tiers A B C
python3 $E/sprint_phase4/analyze_tiered.py

echo "== Phase 6: freeze =="
python3 $E/sprint_phase6/freeze.py

echo "== frozen-artifact guard (post) =="
python3 $E/common/frozen.py verify
echo "done"
