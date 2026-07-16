#!/usr/bin/env bash
set -euo pipefail

python3 revision_v2/experiments/common/frozen.py verify
command -v souffle || true
command -v docker || true
command -v podman || true
command -v colima || true
# The bounded shipped-fact analysis is recorded in limited_agreement.json; the full analyzer
# was not run because the feasibility gate selected Option B.
python3 revision_v2/experiments/common/frozen.py verify
