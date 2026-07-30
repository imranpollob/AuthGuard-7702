"""Inter-rater reliability statistics for completed (non-draft) annotations."""
from __future__ import annotations

from collections import Counter, defaultdict

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
        return 1.0
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
        return 1.0
    return (p_bar - p_e_bar) / (1 - p_e_bar)


def compute_agreement_stats() -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT item_id, reviewer_id, label, is_adjudication FROM annotations WHERE is_draft = 0"
    ).fetchall()
    conn.close()

    by_item = defaultdict(dict)
    for r in rows:
        if r["is_adjudication"]:
            continue
        by_item[r["item_id"]][r["reviewer_id"]] = r["label"]

    dual_reviewed = {item: revs for item, revs in by_item.items() if len(revs) >= 2}
    pairs = []
    equal_rater_lists = []
    for item, revs in dual_reviewed.items():
        reviewer_ids = sorted(revs.keys())[:2]
        pairs.append((revs[reviewer_ids[0]], revs[reviewer_ids[1]]))
        if len(revs) == len(next(iter(dual_reviewed.values()))):
            equal_rater_lists.append(list(revs.values()))

    return {
        "n_items_with_2plus_reviewers": len(dual_reviewed),
        "n_items_total_reviewed": len(by_item),
        "cohens_kappa_first_two_reviewers": cohens_kappa(pairs),
        "fleiss_kappa_equal_rater_subset": fleiss_kappa(equal_rater_lists) if equal_rater_lists else None,
        "raw_agreement_rate": (sum(1 for a, b in pairs if a == b) / len(pairs)) if pairs else None,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(compute_agreement_stats(), indent=2))
