#!/usr/bin/env bash
set -euo pipefail

python3 revision_v2/experiments/common/frozen.py verify
revision_v2/.venv/bin/python revision_v2/experiments/conflicts/analyze_conflicts.py --network
revision_v2/.venv/bin/python revision_v2/experiments/conflicts/abstention_eval.py
revision_v2/.venv/bin/python revision_v2/experiments/label_audit/build_audit_package.py
revision_v2/.venv/bin/python revision_v2/experiments/label_audit/agreement.py
revision_v2/.venv/bin/python revision_v2/experiments/exec_validation/run_exec_validation.py
revision_v2/.venv/bin/python revision_v2/experiments/secondary_controls/run_controls.py
python3 revision_v2/experiments/common/frozen.py verify
