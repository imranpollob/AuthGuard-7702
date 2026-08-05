from revision_v3.experiments.reporting.generate_prelabel_submission_assets import (
    build_prelabel_macros,
)


def test_prelabel_submission_assets_are_hash_bound_and_label_free():
    rendered, report = build_prelabel_macros()
    assert report["status"] == "PRELABEL_SUBMISSION_ASSETS_GENERATED"
    assert report["postcutoff_annotations_accessed"] is False
    assert "\\newcommand{\\CanonicalRows}{2,190}" in rendered
    assert "\\newcommand{\\FinalCompleteRuntimes}{1,063}" in rendered
    assert "\\newcommand{\\FullDCRGPreWarn}{62}" in rendered
    assert "sha256:" in rendered
    assert "final_label" not in rendered.lower()
