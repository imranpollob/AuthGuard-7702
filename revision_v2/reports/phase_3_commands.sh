#!/usr/bin/env bash
set -euo pipefail

python3 revision_v2/experiments/common/frozen.py verify
revision_v2/.venv/bin/python revision_v2/experiments/baselines/run_baselines_ablations.py
revision_v2/.venv/bin/python revision_v2/experiments/uncertainty/bootstrap_baselines.py
revision_v2/.venv/bin/python revision_v2/experiments/family_sensitivity/run_family_sensitivity.py
revision_v2/.venv/bin/python revision_v2/experiments/weighting/run_weighting.py
python3 revision_v2/experiments/common/frozen.py verify
