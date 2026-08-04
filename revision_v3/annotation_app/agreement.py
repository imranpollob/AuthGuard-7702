"""Sample-specific inter-rater reliability and adjudication-completeness reports."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib

from db import get_connection


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """pairs: list of (rater_a_label, rater_b_label) for the same items."""
    if not pairs:
        return None
    labels = sorted({l for pair in pairs for l in pair})
    n = len(pairs)
    observed_agreement = sum(1 for a, b in pairs if a == b) / n
    a_counts = Counter(a for a, _ in pairs)
    b_counts = Counter(b for _, b in pairs)
    expected_agreement = sum((a_counts[l] / n) * (b_counts[l] / n) for l in labels)
    if expected_agreement == 1.0:
        return None  # zero denominator: kappa is undefined, even under perfect agreement
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


def fleiss_kappa(item_label_lists: list[list[str]]) -> float | None:
    """item_label_lists: one list of labels per item, one entry per rater who labeled it.
    Requires the same number of raters per item (Fleiss' original formulation)."""
    if not item_label_lists:
        return None
    n_raters = len(item_label_lists[0])
    if any(len(labels) != n_raters for labels in item_label_lists):
        return None  # unequal raters-per-item; caller should use Cohen's kappa on pairs instead
    categories = sorted({l for labels in item_label_lists for l in labels})
    n_items = len(item_label_lists)

    p_j = {c: 0.0 for c in categories}
    p_i = []
    for labels in item_label_lists:
        counts = Counter(labels)
        p_i_val = sum(counts[c] * (counts[c] - 1) for c in categories) / (n_raters * (n_raters - 1))
        p_i.append(p_i_val)
        for c in categories:
            p_j[c] += counts[c]
    for c in categories:
        p_j[c] /= (n_items * n_raters)

    p_bar = sum(p_i) / n_items
    p_e_bar = sum(v * v for v in p_j.values())
    if p_e_bar == 1.0:
        return None
    return (p_bar - p_e_bar) / (1 - p_e_bar)


MANDATORY_DUAL_REVIEW_SETS = {"pilot", "gold_test", "postcutoff"}


def _item_id_hash(item_ids) -> str:
    return hashlib.sha256("\n".join(sorted(str(value) for value in item_ids)).encode()).hexdigest()


def summarize_agreement(item_rows, annotation_rows, sample_set: str | None = None) -> dict:
    """Build a reliability report from neutral item metadata and submitted annotations."""
    items = {
        str(row["item_id"]): str(row["sample_set"])
        for row in item_rows
        if sample_set is None or str(row["sample_set"]) == sample_set
    }
    by_item: dict[str, dict[str, dict]] = {
        item_id: {"primary": {}, "adjudication": {}} for item_id in items
    }
    for row in annotation_rows:
        item_id = str(row["item_id"])
        if item_id not in by_item:
            continue
        group = "adjudication" if bool(row["is_adjudication"]) else "primary"
        by_item[item_id][group][str(row["reviewer_id"])] = dict(row)

    primary_count_distribution = Counter(
        len(record["primary"]) for record in by_item.values()
    )
    exactly_dual = {
        item_id: record for item_id, record in by_item.items()
        if len(record["primary"]) == 2
    }
    over_reviewed = sorted(
        item_id for item_id, record in by_item.items() if len(record["primary"]) > 2
    )
    reviewer_pair_counts = Counter(
        tuple(sorted(record["primary"])) for record in exactly_dual.values()
    )
    pair_labels: list[tuple[str, str]] = []
    item_pairs: dict[str, tuple[str, str]] = {}
    disagreements: list[str] = []
    unanimous: list[str] = []
    for item_id, record in sorted(exactly_dual.items()):
        reviewer_ids = sorted(record["primary"])
        labels = tuple(record["primary"][reviewer]["label"] for reviewer in reviewer_ids)
        pair_labels.append(labels)
        item_pairs[item_id] = labels
        (unanimous if labels[0] == labels[1] else disagreements).append(item_id)

    single_pair = len(reviewer_pair_counts) == 1
    cohen_value = cohens_kappa(pair_labels) if single_pair and pair_labels else None
    if not pair_labels:
        cohen_reason = "NO_EXACTLY_DUAL_REVIEWED_ITEMS"
    elif not single_pair:
        cohen_reason = "MULTIPLE_REVIEWER_PAIRS_COULD_NOT_BE_COMBINED_AS_COHEN_KAPPA"
    elif cohen_value is None:
        cohen_reason = "UNDEFINED_ZERO_EXPECTED_DISAGREEMENT_DENOMINATOR"
    else:
        cohen_reason = "VALID_SINGLE_FIXED_REVIEWER_PAIR"

    adjudicated_disagreements = []
    pending_adjudications = []
    multiple_adjudications = []
    unexpected_adjudications = []
    final_labels: list[str] = []
    final_indeterminate_reasons: list[str] = []
    for item_id in unanimous:
        record = by_item[item_id]
        if record["adjudication"]:
            unexpected_adjudications.append(item_id)
        final_reviewer = sorted(record["primary"])[0]
        final = record["primary"][final_reviewer]
        final_labels.append(final["label"])
        if final.get("indeterminate_reason"):
            final_indeterminate_reasons.append(str(final["indeterminate_reason"]))
    for item_id in disagreements:
        adjudications = by_item[item_id]["adjudication"]
        if len(adjudications) == 1:
            adjudicated_disagreements.append(item_id)
            final = next(iter(adjudications.values()))
            final_labels.append(final["label"])
            if final.get("indeterminate_reason"):
                final_indeterminate_reasons.append(str(final["indeterminate_reason"]))
        elif len(adjudications) == 0:
            pending_adjudications.append(item_id)
        else:
            multiple_adjudications.append(item_id)
    for item_id, record in by_item.items():
        if item_id not in exactly_dual and record["adjudication"]:
            unexpected_adjudications.append(item_id)

    marginal_by_reviewer: dict[str, Counter] = defaultdict(Counter)
    for record in exactly_dual.values():
        for reviewer_id, annotation in record["primary"].items():
            marginal_by_reviewer[reviewer_id][str(annotation["label"])] += 1

    confusion = None
    if single_pair and reviewer_pair_counts:
        fixed_pair = next(iter(reviewer_pair_counts))
        categories = sorted({label for pair in pair_labels for label in pair})
        matrix = {
            label_a: {label_b: 0 for label_b in categories} for label_a in categories
        }
        for label_a, label_b in pair_labels:
            matrix[label_a][label_b] += 1
        confusion = {
            "reviewer_a": fixed_pair[0],
            "reviewer_b": fixed_pair[1],
            "rows_reviewer_a_columns_reviewer_b": matrix,
        }

    mandatory = sample_set in MANDATORY_DUAL_REVIEW_SETS
    all_exactly_dual = len(exactly_dual) == len(items)
    all_disagreements_resolved = not pending_adjudications and not multiple_adjudications
    clean_adjudication = not unexpected_adjudications
    if not items:
        status = "EMPTY_NO_ITEMS"
    elif mandatory and all_exactly_dual and all_disagreements_resolved and clean_adjudication:
        status = "COMPLETE_DUAL_REVIEW_AND_ADJUDICATION"
    elif mandatory:
        status = "NOT_READY_DUAL_REVIEW_OR_ADJUDICATION_INCOMPLETE"
    else:
        status = "DESCRIPTIVE_NONMANDATORY_REVIEW"

    return {
        "status": status,
        "sample_set": sample_set or "ALL",
        "item_ids_sha256": _item_id_hash(items),
        "n_manifest_items": len(items),
        "primary_review_count_distribution": {
            str(key): value for key, value in sorted(primary_count_distribution.items())
        },
        "n_exactly_dual_reviewed": len(exactly_dual),
        "n_over_reviewed": len(over_reviewed),
        "over_reviewed_item_ids": over_reviewed,
        "reviewer_pair_counts": {
            "|".join(pair): count for pair, count in sorted(reviewer_pair_counts.items())
        },
        "n_primary_unanimous": len(unanimous),
        "n_primary_disagreements": len(disagreements),
        "raw_agreement_rate": (
            len(unanimous) / len(exactly_dual) if exactly_dual else None
        ),
        "cohens_kappa": cohen_value,
        "cohens_kappa_interpretation": cohen_reason,
        "fleiss_kappa_two_rater_items": (
            fleiss_kappa([list(pair) for pair in pair_labels]) if pair_labels else None
        ),
        "primary_label_marginals_by_reviewer": {
            reviewer: dict(sorted(counts.items()))
            for reviewer, counts in sorted(marginal_by_reviewer.items())
        },
        "primary_confusion_matrix": confusion,
        "n_adjudicated_disagreements": len(adjudicated_disagreements),
        "n_pending_adjudications": len(pending_adjudications),
        "n_multiple_adjudications": len(multiple_adjudications),
        "n_unexpected_adjudications_on_unanimous_items": len(unexpected_adjudications),
        "adjudication_rate_among_disagreements": (
            len(adjudicated_disagreements) / len(disagreements) if disagreements else None
        ),
        "pending_adjudication_item_ids": pending_adjudications,
        "final_label_counts_on_resolved_dual_items": dict(sorted(Counter(final_labels).items())),
        "final_indeterminate_reason_counts": dict(
            sorted(Counter(final_indeterminate_reasons).items())
        ),
        "claim_boundary": (
            "Agreement is computed on pre-adjudication primary labels. Adjudicator labels are "
            "used only for resolution counts and final-label summaries."
        ),
    }


def compute_agreement_stats(sample_set: str | None = None) -> dict:
    conn = get_connection()
    item_rows = conn.execute("SELECT item_id, sample_set FROM items ORDER BY item_id").fetchall()
    annotation_rows = conn.execute(
        "SELECT item_id, reviewer_id, label, indeterminate_reason, is_adjudication "
        "FROM annotations WHERE is_draft = 0 ORDER BY item_id, is_adjudication, reviewer_id"
    ).fetchall()
    conn.close()
    return summarize_agreement(item_rows, annotation_rows, sample_set)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("sample_set", nargs="?", default=None)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = compute_agreement_stats(args.sample_set)
    if args.output:
        with open(args.output, "w") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
    print(json.dumps(report, indent=2, sort_keys=True))
