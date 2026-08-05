"""Pre-label gate for the post-cutoff annotation sample."""
from __future__ import annotations

import hashlib
import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_UNLOCK_PATH = os.path.join(
    REPO_ROOT, "revision_v3", "results", "postcutoff_snapshot",
    "postcutoff_review_unlock.json",
)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repository_file(relative_path: object, repo_root: str, label: str) -> tuple[str | None, str | None]:
    if not isinstance(relative_path, str) or not relative_path or os.path.isabs(relative_path):
        return None, f"{label} path is not repository-relative"
    root = os.path.realpath(repo_root)
    resolved = os.path.realpath(os.path.join(root, relative_path))
    try:
        contained = os.path.commonpath([root, resolved]) == root
    except ValueError:
        contained = False
    if not contained or not os.path.isfile(resolved):
        return None, f"{label} is missing or outside the repository"
    return resolved, None


def postcutoff_review_unlock_status(
    unlock_path: str = DEFAULT_UNLOCK_PATH,
    *,
    repo_root: str = REPO_ROOT,
) -> tuple[bool, str]:
    if not os.path.exists(unlock_path):
        return False, "post-cutoff scores and retraining provenance are not frozen"
    try:
        with open(unlock_path) as handle:
            unlock = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        return False, f"invalid post-cutoff review unlock: {error}"
    if unlock.get("status") != "POSTCUTOFF_REVIEW_UNLOCKED_AFTER_SCORING_FREEZE":
        return False, "post-cutoff review unlock has an invalid status"
    if unlock.get("provenance_status") != "POSTCUTOFF_SCORING_PROVENANCE_VERIFIED":
        return False, "post-cutoff scoring provenance was not verified"
    manifest_path, error = _repository_file(
        unlock.get("training_manifest"), repo_root, "post-cutoff training manifest"
    )
    if error:
        return False, error
    assert manifest_path is not None
    if _sha256_file(manifest_path) != unlock.get("training_manifest_sha256"):
        return False, "post-cutoff training-manifest hash mismatch"
    try:
        with open(manifest_path) as handle:
            training = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        return False, f"invalid post-cutoff training manifest: {error}"
    if training.get("status") != "FROZEN_POSTCUTOFF_RETRAINING_COMPLETE":
        return False, "post-cutoff training manifest is not complete"
    if training.get("method_frozen_before_postcutoff_labels") is not True:
        return False, "post-cutoff method was not attested frozen before labels"
    if training.get("postcutoff_labels_accessed") is not False:
        return False, "post-cutoff label-access attestation is invalid"
    if training.get("predictions_sha256") != unlock.get("predictions_sha256"):
        return False, "post-cutoff prediction hash mismatch between locks"
    predictions_path, error = _repository_file(
        training.get("predictions_path"), repo_root, "post-cutoff predictions"
    )
    if error:
        return False, error
    assert predictions_path is not None
    if _sha256_file(predictions_path) != training.get("predictions_sha256"):
        return False, "post-cutoff prediction file hash mismatch"
    return True, "post-cutoff scores and retraining provenance are frozen"
