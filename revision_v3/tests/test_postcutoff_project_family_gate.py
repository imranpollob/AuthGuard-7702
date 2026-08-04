from __future__ import annotations

import pandas as pd
import pytest

from revision_v3.experiments.temporal_v2.validate_postcutoff_project_families import (
    build_audit_template,
    validate_project_family_audit,
)


def _manifest():
    return pd.DataFrame([
        {"item_id": "ethereum:0x01", "family_id": "T0001"},
        {"item_id": "ethereum:0x02", "family_id": "T0002"},
    ])


def test_unresolved_template_fails_closed():
    audit = build_audit_template(_manifest())
    with pytest.raises(ValueError, match="UNRESOLVED"):
        validate_project_family_audit(_manifest(), audit, {"F00001"})


def test_confirmed_project_family_materializes_union_of_training_holds():
    audit = build_audit_template(_manifest())
    audit["postcutoff_project_family_id"] = "PF_ZERODEV"
    audit["provenance_status"] = "CONFIRMED"
    audit["evidence_reference"] = ["https://example.org/a", "https://example.org/b"]
    audit["auditor_id"] = "A1"
    audit["related_canonical_family_ids"] = ["F00001", "F00002"]
    report = validate_project_family_audit(_manifest(), audit, {"F00001", "F00002"})
    hold = report["project_family_holds"]["PF_ZERODEV"]
    assert report["status"] == "READY_FOR_PROJECT_FAMILY_RETRAINING_HOLDS"
    assert hold["canonical_family_ids_to_hold_out"] == ["F00001", "F00002"]
    assert hold["item_ids"] == ["ethereum:0x01", "ethereum:0x02"]


def test_unknown_canonical_family_is_rejected():
    audit = build_audit_template(_manifest())
    audit["postcutoff_project_family_id"] = "PF_X"
    audit["provenance_status"] = "CONFIRMED"
    audit["evidence_reference"] = "dossier:x"
    audit["auditor_id"] = "A1"
    audit["related_canonical_family_ids"] = "F99999"
    with pytest.raises(ValueError, match="unknown canonical family"):
        validate_project_family_audit(_manifest(), audit, {"F00001"})
