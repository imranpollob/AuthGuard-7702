#!/usr/bin/env bash
# Reproduce the entire AuthGuard-7702 experimental section. Deterministic (seed=7702).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONHASHSEED=0
echo "== A. freeze families ==";      python3 pipeline/01_freeze_families.py
echo "== B. features ==";             python3 pipeline/02_features.py
echo "== C. detection (LFO) ==";      python3 pipeline/03_detection.py
echo "== D. mutation spine ==";       python3 pipeline/04_mutations.py
echo "== E. supporting ==";           python3 pipeline/05_supporting.py
echo "== F. figures ==";              python3 pipeline/06_figures.py
echo "== F. summary ==";              python3 pipeline/07_summary.py
echo "DONE. See results_summary.md and figures/."
