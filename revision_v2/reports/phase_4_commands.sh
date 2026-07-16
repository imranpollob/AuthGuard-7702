#!/usr/bin/env bash
set -euo pipefail

python3 revision_v2/experiments/common/frozen.py verify
revision_v2/.venv/bin/python revision_v2/experiments/gateA/run_gateA.py
revision_v2/.venv/bin/python revision_v2/experiments/gateA/gateA_verdict.py
revision_v2/.venv/bin/python revision_v2/experiments/gateB/run_gateB.py
python3 revision_v2/experiments/common/frozen.py verify
