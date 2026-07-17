#!/usr/bin/env bash
set -euo pipefail

python3 revision_v2/experiments/common/frozen.py verify
revision_v2/.venv/bin/python revision_v2/experiments/common/validate_harness.py
python3 revision_v2/experiments/common/frozen.py verify
