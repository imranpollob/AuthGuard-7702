#!/usr/bin/env bash
set -euo pipefail

python3 revision_v2/experiments/common/frozen.py verify
revision_v2/.venv/bin/python revision_v2/experiments/common/validate_harness.py
revision_v2/.venv/bin/python revision_v2/experiments/gdet_v2/run_gdet_v2.py
revision_v2/.venv/bin/python revision_v2/experiments/gmut_v2/run_gmut_v2.py
revision_v2/.venv/bin/python revision_v2/experiments/uncertainty/bootstrap_gdet.py
revision_v2/.venv/bin/python revision_v2/experiments/gadv_v2/run_gadv_v2.py
revision_v2/.venv/bin/python revision_v2/experiments/uncertainty/bootstrap_gadv.py
python3 revision_v2/experiments/common/frozen.py verify
