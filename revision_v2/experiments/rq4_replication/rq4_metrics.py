#!/usr/bin/env python3
"""Shared metric and contrast definitions for the RQ4 three-seed replication.

Every definition here is read off the existing pipeline rather than re-invented:

  eligibility      clean_score >= validation-fitted 5% FPR threshold  (clean_detected)
  attack success   clean_detected AND adversarial_score < threshold
  marginal ASR     mean(attack_success) over that model's own eligible observations
  paired contrast  mean of per-observation differences over the COMMON population that
                   both compared models detect cleanly, family-clustered bootstrap
  robust recall    (# positives clean-detected AND still detected after the strongest
                   attack) / (# all positive observations)

The bootstrap mirrors the procedure already used for the published contrasts: resample
bytecode families with replacement, apply the same multiplicities to both members of a
pair, 10,000 replicates, seeded deterministically from the contrast identity.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

NBOOT = 10_000
SEARCH_METHODS = ["random_search", "beam_search"]
KEY = ["seed", "fold", "sid"]
MODELS = ["chunk_attention_16384", "chunk_mean_16384", "flat_control_16384"]


def marginal(frame, model, method):
    """Marginal ASR over the model's own cleanly-detected observations."""
    g = frame[(frame.target_model == model) & (frame.method == method)]
    e = g[g.clean_detected]
    return dict(
        model=model, method=method,
        n_observations=int(len(g)),
        n_eligible=int(len(e)),
        n_eligible_families=int(e.family_id.nunique()) if len(e) else 0,
        successes=int(e.attack_success.sum()) if len(e) else 0,
        ASR=float(e.attack_success.mean()) if len(e) else np.nan)


def clean_detection(frame, model):
    g = frame[frame.target_model == model].drop_duplicates(KEY)
    return float(g.clean_detected.mean()), int(len(g))


def strongest(frame, model, methods=SEARCH_METHODS):
    """Per-observation strongest attack (lowest adversarial score) within `methods`."""
    g = frame[(frame.target_model == model) & (frame.method.isin(methods))]
    if not len(g):
        return None
    idx = g.groupby(KEY).adversarial_score.idxmin()
    best = g.loc[idx].copy()
    best["attack_success"] = best.clean_detected & (best.adversarial_score < best.threshold)
    return best


def robust_recall(frame, model, methods=SEARCH_METHODS):
    """Direct source-level robust recall over ALL positive observations."""
    best = strongest(frame, model, methods)
    if best is None:
        return dict(model=model, robust_recall=np.nan)
    detected = best.clean_detected.to_numpy(bool)
    still = best.adversarial_score.to_numpy() >= best.threshold.to_numpy()
    total = int(len(best))
    survived = int((detected & still).sum())
    return dict(model=model, n_positive_observations=total, n_survived=survived,
                robust_recall=survived / total if total else np.nan)


def _family_bootstrap(fams, delta, eligible, seed_material, nboot=NBOOT):
    uniq = np.asarray(sorted(pd.unique(fams)))
    index = {f: i for i, f in enumerate(uniq)}
    row_family = np.asarray([index[f] for f in fams])
    rng = np.random.default_rng(int.from_bytes(hashlib.blake2b(
        seed_material.encode(), digest_size=8).digest(), "little"))
    draws = np.empty(nboot)
    for r in range(nboot):
        counts = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
        w = counts[row_family] * eligible
        total = w.sum()
        draws[r] = (w * delta).sum() / total if total else np.nan
    draws = draws[np.isfinite(draws)]
    return draws, len(uniq)


def paired_contrast(frame, left, right, method, label, nboot=NBOOT):
    """ASR(left) - ASR(right) over the COMMON cleanly-detected population."""
    a = frame[(frame.target_model == left) & (frame.method == method)].set_index(KEY).sort_index()
    b = frame[(frame.target_model == right) & (frame.method == method)].set_index(KEY).sort_index()
    shared = a.index.intersection(b.index)
    if not len(shared):
        return None
    a, b = a.loc[shared], b.loc[shared]
    eligible = a.clean_detected.to_numpy(bool) & b.clean_detected.to_numpy(bool)
    if not eligible.any():
        return None
    sa = a.attack_success.to_numpy(float)
    sb = b.attack_success.to_numpy(float)
    draws, n_fam_all = _family_bootstrap(a.family_id.to_numpy(), sa - sb, eligible,
                                         f"rq4:{label}:{left}:{right}:{method}", nboot)
    ci = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
    return dict(
        label=label, contrast=f"{left} - {right}", method=method,
        left_ASR_on_common=float(sa[eligible].mean()),
        right_ASR_on_common=float(sb[eligible].mean()),
        difference=float((sa[eligible] - sb[eligible]).mean()),
        ci_low=ci[0], ci_high=ci[1],
        excludes_zero=bool(ci[0] > 0 or ci[1] < 0),
        n_common_observations=int(len(shared)),
        n_paired_eligible=int(eligible.sum()),
        n_families_eligible=int(pd.unique(a.family_id.to_numpy()[eligible]).size),
        bootstrap_replicates=int(len(draws)))
