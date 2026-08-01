# ML vs. Static Analysis: Positioning

**LABEL_SOURCE=LLM_PROVISIONAL where evidence is cited below. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

This document sets out the defensible framing for AuthGuard's role relative to static/semantic
analysis, grounded in evidence collected in this pipeline pass (Parts 1-2, 6, 9, 10, 14)
rather than asserted claims.

## The claim this project does NOT make

Semantic static analysis (full decompilation, control-flow tracing, guard verification —
exactly the process built out in Parts 1-2 and used to hand-derive the Pilot's findings) is
not something AuthGuard replaces, and it is not claimed to be infeasible before authorization.
This pipeline's own evidence contradicts that claim directly: every one of the 230
Pilot/Gold-Dev/Gold-Test items *was* semantically analyzed offline, before any authorization
decision, using only public data (bytecode + free verified-source/RPC services) — see
`revision_v3/human_eval/*_code_evidence/`. Semantic analysis is available pre-authorization
whenever bytecode and basic tooling access exist.

## What semantic analysis actually costs, measured in this pipeline

- **Toolchain complexity**: a working pipeline needs a decompiler (evmole), a selector
  database (4byte.directory), a source registry (Sourcify/Blockscout), and an RPC client for
  proxy resolution — 4 independent external dependencies, two of them live network services
  with no uptime guarantee (Part 11's Base collection stalled repeatedly on exactly this kind
  of dependency; see `TEMPORAL_COLLECTION_FINAL_STATUS.md`).
- **Coverage gap**: 0/20 Pilot, 6/60 Gold-Dev (10%), 18/150 Gold-Test (12%) items had verified
  source at all — the overwhelming majority require decompilation, which the guard tracer
  built for this project could resolve to a definite GUARDED/OPEN finding for 17/20 Pilot
  items by hand and the majority (though not all — see `guard_trace_overall_status`
  distributions in `source_inventory.csv`) of Gold-Dev/Gold-Test items automatically.
  A meaningful fraction (`AMBIGUOUS` status: 5/60 Gold-Dev, 3/150 Gold-Test) resisted
  automated tracing entirely.
- **Latency**: the automated evidence pipeline (source check + decompile + guard trace) for
  one item took on the order of seconds to tens of seconds (dominated by external HTTP/RPC
  round-trips, not local compute) — clearly too slow for the sub-authorization-transaction
  timing budget of a wallet UI warning, and not something that scales to screening every
  contract that requests an EIP-7702 delegation across all chains in real time.

## Where AuthGuard fits

AuthGuard (Part 14, measured on this machine): ~2.9ms median CPU end-to-end latency,
116 items/sec single-process throughput, no network dependency, no decompiler dependency —
orders of magnitude cheaper and faster than the semantic pipeline above, at the cost of being
a compact score, not an explanation.

- **Real measured accuracy vs. semantic-derived provisional labels** (Part 9, Gold-Test,
  LLM_PROVISIONAL): AUPRC 0.963 [0.928, 0.991] for `authguard_sequence_dense`, materially
  above chance but with real, quantified limits (recall 0.336 at the frozen 5%-FPR-derived
  threshold — see caveats in `LLM_PROVISIONAL_GOLD_TEST_REPORT.md`).
- **Calibration and uncertainty routing** (Part 10, cascade): the escalation-band policy
  (`C_authguard_first_rule_escalation`) routed 37.0% of Gold-Test items to a second check while
  resolving the remaining 63.0% from the AuthGuard score alone — a concrete, measured workload
  reduction, not an assumption.
- **Prioritization**: AuthGuard's score is what let this pipeline decide, cheaply, which
  Gold-Dev/Gold-Test items most needed the expensive semantic trace's full attention (the
  guard-tracer's `any_sensitive_open`/`any_ambiguous` flags play exactly this role already).

## The defensible framing (verbatim, for the manuscript)

- Semantic static analysis **can** be used before authorization when bytecode and toolchain
  access are available — this project's own evidence pipeline is proof by construction.
- AuthGuard provides a compact, score-producing triage mechanism: sub-3ms, no external
  dependency, applicable even when the semantic toolchain (RPC/decompiler/registry access) is
  unavailable, degraded, or too slow for the decision window.
- Uncertain or high-risk cases (by score, or by an explicit UNCERTAIN provisional label) can
  be escalated to deeper semantic analysis — Part 10's cascade policies are a concrete
  instantiation of this, not a proposal.
- The benefit is **measured workload reduction and prioritization** (Part 10's escalation
  rates; Part 14's latency/throughput numbers), not a claim of replacing semantic analysis.
- The two are complementary layers of the same pipeline, not substitutes: this project builds
  and uses both, and reports each on its own terms.

## Honest limitation

The cascade policy's escalation band was tuned on Gold-Dev (47 items) — small enough that its
generalization to Gold-Test, while evaluated once and not re-tuned (per protocol), should be
read with the same small-sample caution flagged throughout Part 7/8's retraining results.
