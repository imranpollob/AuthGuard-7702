# Artifact Description, Limitations, Ethics, Conclusion

## Artifact description

Released: (1) the full evidence-collection pipeline (`evidence_pipeline.py` + per-sample-set
enrichment drivers), reproducible against any EIP-7702 delegate address given chain + address;
(2) the LLM-provisional labeling protocol and its 230-item output, with full evidence
citations; (3) `authguard_sequence_dense` model weights, training harness, and the one-command
reference-pipeline rerun script supporting 3 label sources; (4) the human-review Excel
workbooks (structurally blinded to model scores and source labels) for independent
verification; (5) the legitimate-control dataset (30 verified/candidate real-world EIP-7702
deployments); (6) the deployment-benchmark harness including a working ONNX export path.

## Limitations

- **All quantitative results in this pipeline pass rest on LLM-provisional labels**, not
  independent human review — the single largest limitation, acknowledged throughout rather
  than hedged.
- **The retraining/model-selection exercise (Part 7-8) used only 47 Gold-Dev binary items**
  — small enough that its own headline finding (a competitive-AUPRC model with a degenerate
  operating threshold) is itself evidence of this limitation's practical bite.
- **Temporal collection is partial** at the time of this pipeline pass (Ethereum ~2.3% of
  target window scanned; Base collection stalled on indexed-API reliability) — background
  jobs remain running and resumable, but no temporal claim in this manuscript should be
  treated as based on complete coverage.
- **The automated guard-tracer is a heuristic**, not a formal verifier — it correctly flagged
  itself AMBIGUOUS on 5/60 Gold-Dev and 3/150 Gold-Test items rather than forcing a guess, but
  its OPEN/GUARDED classification on the remainder has not been independently audited beyond
  the Pilot batch's hand-verified 20 items.
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
throughout this pipeline (Sourcify, Blockscout, 4byte.directory, public RPC endpoints) used
only public, read-only, rate-limit-respecting requests.

## Conclusion

AuthGuard demonstrates that a compact (97,646-parameter), fast (sub-3ms CPU) neural model can
provide a meaningful, calibratable-with-caveats triage signal for EIP-7702 delegate
authorization risk, positioned explicitly as a complement to — not a replacement for — the
semantic decompilation-and-guard-tracing pipeline this same project built and used to
construct its own evaluation labels. The provisional results in this manuscript are a
complete, honestly-caveated dry run of the full research pipeline, built specifically so
that independent human review, once complete, can be substituted in with one command and no
further pipeline engineering.
