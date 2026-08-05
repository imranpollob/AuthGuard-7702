# Artifact Description, Limitations, Ethics, Conclusion

## Artifact description

The artifact contains: (1) the evidence-collection pipeline and per-sample-set enrichment
drivers; (2) the explicitly provisional LLM labeling protocol and outputs; (3)
`authguard_sequence_dense`, DCRG extraction, training, calibration, and evaluation code; (4) a
server-rendered annotation application whose packets exclude model scores, inherited labels,
and DCRG outputs; (5) frozen Gold-Test and post-cutoff manifests with dual-review/adjudication
gates; (6) a legitimate-control dataset covering 30 deployments; and (7) a frozen Ethereum
post-cutoff snapshot, recovered authority/delegate pairs, score-blind project-provenance
worklists, and pre-label retraining locks. Human labels and post-cutoff scores are absent until
their declared gates are completed; the artifact does not package placeholders as results.

## Limitations

- **All quantitative results in this pipeline pass rest on LLM-provisional labels**, not
  independent human review — the single largest limitation, acknowledged throughout rather
  than hedged.
- **The retraining/model-selection exercise (Part 7-8) used only 47 Gold-Dev binary items**
  — small enough that its own headline finding (a competitive-AUPRC model with a degenerate
  operating threshold) is itself evidence of this limitation's practical bite.
- **The authoritative post-cutoff snapshot is Ethereum-only.** Its hydrated checkpoint covers
  283,244 blocks through block 24,641,536 and contains 517,930 type-4 transactions without
  scan-RPC errors, but it does not establish cross-chain external validity. Of 734 recovered
  valid signer/delegate pairs, 708 had code at first observation. The frozen 150-item review
  sample remains unusable for accuracy claims until project-family provenance, pre-label
  retraining, dual review, and adjudication are complete.
- **The DCRG extractor is a bounded analyzer, not a formal verifier.** Only 670/2,190 primary
  samples have `COMPLETE` traversal coverage; the remaining 1,520 are explicitly `PARTIAL`.
  This is why the policy defers incomplete below-threshold cases rather than calling them safe.
- **The inherited primary labels overlap the semantic evidence represented by DCRG.** The
  strong primary-fold DCRG result is therefore an engineering diagnostic susceptible to label
  circularity, not independent evidence that semantic risk was detected.
- **Gold-Dev and Gold-Test are sampled from the canonical primary corpus.** They must use each
  family's held-out-fold checkpoint and cannot be described as fully external data. The old
  all-fold-ensemble reports were invalid and have been replaced with provenance-matched scores.
- **The static rule comparison and cascade design used only 138-150 Gold-Test items** — no
  claim in this manuscript should be read as applying beyond this specific evaluation sample's
  distribution (heavily curated toward `known_disagreement`-flagged, ambiguous cases, not a
  random sample of all EIP-7702 delegates).

## Ethics

This project analyzes only public, on-chain bytecode and publicly documented project
deployments; no private keys, user data, or non-public information were accessed. The
legitimate-control dataset documents real, named projects' deployment addresses drawn from
their own public documentation — no claim about any named project's security beyond what is
explicitly cited (verified source presence, runtime-hash match) is made. Live network calls
throughout this pipeline (Sourcify, Blockscout, 4byte.directory, and public RPC endpoints) use
public, read-only, rate-limited requests. Public verification names, tags, and proxy
relationships are retained only as audit leads; they are not automatically treated as project
ownership or security evidence.

## Conclusion

AuthGuard-7702 currently demonstrates a reproducible coverage-aware screening design: a compact
bytecode model, an EIP-7702-specific contextual risk representation, provenance-safe
family-held-out scoring, and an explicit deferral policy. It does not yet demonstrate
independent semantic validity. That stronger conclusion is gated on adjudicated human labels
and genuinely post-cutoff project families; until those gates pass, the quantitative results
are a complete engineering dry run rather than the final acceptance claim.
