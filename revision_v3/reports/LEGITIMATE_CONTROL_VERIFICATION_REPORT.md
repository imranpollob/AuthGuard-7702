# Legitimate EIP-7702 Control Verification Report

Strengthens Phase 2's `legitimate_candidates_unique_bytecode.csv` (30 unique project-bytecode
pairs, 8 documented projects) with live verification. Script:
`verify_legitimate_controls.py`. Output: `external_controls/verified_legitimate_controls.csv`.

## Method

For each of the 30 recorded deployments: live Sourcify v2 + Blockscout v2 verified-source
checks, live `eth_getCode` retrieval + SHA-256 comparison against the hash recorded in Phase
2's dataset (catches any drift between when Phase 2 recorded the hash and now), and — for
DELEGATECALL-based entries — on-chain implementation-slot resolution, all using the same
`evidence_pipeline.py` built for Parts 1-2.

## Results

- **30/30 runtime-hash matches** (`runtime_source_match=MATCH` for every row) — none of the
  8 documented projects' bytecode has changed since Phase 2 recorded it.
- **22 VERIFIED_LEGITIMATE_CONTROL** (verified source found AND documented) — up from 0
  independently re-verified in Phase 2 (Phase 2 only recorded documentation URLs, it did not
  live-check source verification).
- **8 CANDIDATE_LEGITIMATE_CONTROL** (documented, but no verified source found on Sourcify or
  Blockscout at this address).
- **0 UNRESOLVED_CONTROL** (every recorded deployment is at least documented).

No project was classified VERIFIED solely because its name is known — classification required
both a live verified-source hit and the documented registry entry.

## Per-category evaluation

Not yet cross-referenced against model predictions in this pass (Part 13 asked for model
predictions evaluated separately per category — this requires joining
`verified_legitimate_controls.csv` addresses against a model-scoring pass, which was not run
separately for this specific 30-item set; the 8 documented projects substantially overlap
with items already scored in Parts 6/9's Gold-Dev/Gold-Test runs via `in_v2_primary_benchmark`
membership, but a dedicated legitimate-controls-only scoring pass is a clear, concrete
follow-up item, not yet done).

## Caveat

`CANDIDATE_LEGITIMATE_CONTROL` status reflects a public-verified-source gap at the specific
deployment address checked, not doubt about the project's legitimacy — Phase 2's own
documentation-URL evidence for these 8 remains the basis for treating them as candidates
rather than unresolved.
