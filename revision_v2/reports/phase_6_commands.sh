#!/usr/bin/env bash
set -euo pipefail

python3 revision_v2/experiments/common/frozen.py verify
revision_v2/.venv/bin/python revision_v2/experiments/operational/run_operational.py
revision_v2/.venv/bin/python revision_v2/experiments/manuscript/generate_tables.py
revision_v2/.venv/bin/python revision_v2/experiments/manuscript/integrate_manuscript.py
revision_v2/.venv/bin/python revision_v2/experiments/manuscript/static_tex_audit.py
revision_v2/.venv/bin/python revision_v2/experiments/artifact/sanitize_manifests.py
revision_v2/.venv/bin/python revision_v2/experiments/artifact/build_artifact_manifest.py
revision_v2/.venv/bin/python revision_v2/experiments/artifact/audit_anonymity.py
# Fixed-point pass: refresh phase ledgers after the audit exists, include that deterministic
# result in the artifact ledger, then re-audit the resulting ledger.
revision_v2/.venv/bin/python revision_v2/experiments/artifact/refresh_report_manifest_hashes.py
revision_v2/.venv/bin/python revision_v2/experiments/artifact/build_artifact_manifest.py
revision_v2/.venv/bin/python revision_v2/experiments/artifact/audit_anonymity.py
revision_v2/.venv/bin/python revision_v2/experiments/artifact/verify_report_manifests.py
python3 revision_v2/experiments/common/frozen.py verify
