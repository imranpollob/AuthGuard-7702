# Phase 1A — Claim-Correction Audit (manuscript edits deferred to Phase 6C)

Source: `paper_build/overleaf/main.tex` (frozen; line numbers as of ledger hash). Replacement
wording is final-candidate text; numeric placeholders `{v2:…}` are filled from Phase 1–3
machine-readable outputs at integration time. Supported-positioning principles: superiority
only over evaluated bytecode baselines; low local scoring cost on the tested platform;
improvement under specified held-out conditions; task-aligned family-aware evaluation;
complementary pre-authorization screening.

## C1 — Abstract, line 21 (final sentence) — UNSUPPORTED (production-ready / robust)
Current: "…lightweight, sub-10ms bytecode scoring can serve as a robust, production-ready
pre-authorization warning signal."
Replace with: "…lightweight bytecode scoring — averaging ~3.4 ms per contract on the tested
laptop-class hardware — can serve as a complementary pre-authorization screening signal
within the evaluated conditions."
Reason: no wallet integration, no deployment evaluation, no arbitrary-adversary robustness.

## C2 — Abstract, line 21 — "significantly recovers … while reducing false positives"
Replace with wording bound to the donor-isolated v2 result once known, e.g.:
"Under the held-out pure-flooding stress test, source-balanced augmentation with
partition-isolated donors changes recall from {v2:F200_M0_recall} to {v2:F200_aug_recall}
(family-clustered 95% CI on the difference: {v2:CI})."
Reason: v1 augmented numbers are donor-confounded (single shared donor); "significantly"
must be tied to the v2 CI; FPR direction must match v2 evidence.

## C3 — Contributions, line 47 — "sub-10ms latency, enabling real-time screening integration"
Replace with: "The measured local scoring path (feature extraction plus prediction for
preloaded bytecode) averages 3.4 ms per contract on an Apple M1; end-to-end wallet latency
is not evaluated."
Reason: "enabling real-time … integration" asserts an unevaluated system property.

## C4 — Contribution/positioning, lines 43 and 61 — "bridges the gap … sub-second … without
blocking real-time interactive workflows" and "While these declarative analyses are
powerful, they are computationally intensive."
Replace with: "AuthGuard is a lightweight local screening stage intended to complement
declarative analyzers, whose runtime we do not measure; the two approaches consume different
information and provide different guarantees." (Drop "computationally intensive" unless
Phase 5 Option A produces measured timings; keep the existing no-reproduction disclaimer.)
Reason: relative-cost claim about the reference pipeline is unmeasured (Phase 5 fork).

## C5 — RQ5, line 400 — "Crucially, this sub-10ms latency proves that AuthGuard-7702 can be
seamlessly integrated into real-time wallet authorization flows without degrading the user
experience."
Replace with: "These measurements indicate that local scoring is unlikely to dominate an
interactive authorization flow on comparable hardware; wallet-level latency, integration,
and user experience remain unevaluated."
Reason: "proves", "seamlessly", "without degrading the user experience" are all unsupported
(the adjacent sentence already scopes the measurement correctly — this sentence contradicts it).

## C6 — Conclusion, line 432 — "Despite these bounds, AuthGuard establishes a robust, highly
efficient AI-driven pipeline for pre-authorization screening, setting a methodological
benchmark for future smart-contract vulnerability tools."
Replace with: "Within these bounds, AuthGuard provides a task-aligned, dependence-aware
evaluation framework and a lightweight scoring baseline for pre-authorization screening of
EIP-7702 delegates, against which future methods can be compared under the released
protocol."
Reason: "robust", "highly efficient", "establishes … benchmark" overstate; the framework and
released protocol are the supportable artifacts.

## C7 — Contribution bullet, line 49 — G-ADV numbers
The quoted improvements (0.561/0.484/0.217 → 0.758/0.727/0.174) come from donor-confounded
v1 runs. Replace with donor-isolated v2 numbers; retain the statement that the compound
M3-plus-F200 condition is evaluated (it WILL be in v2 — update from "remain unresolved" to
the measured outcome).

## C8 — Sections/*.tex copies
`paper_build/sections/{abstract,introduction,evaluation,discussion,conclusion}.tex` contain
pre-assembly copies of the same sentences; apply identical corrections or retire the copies
from the build to avoid divergence.

## Statements verified as already correctly scoped (keep)
- line 61/75: no reproduction of the full USENIX pipeline; no speedup claim.
- line 102: checker is syntactic; compound condition disclaimer (update per C7 once v2 runs).
- line 249: "structure-preserving under the repository's opcode-skeleton checker".
- line 383/417: augmentation direction-only claims tied to family-clustered CIs (update to v2).
- line 421-427: label-circularity and deployment-boundary paragraphs.
- line 423: independent validation verdict INSUFFICIENT DATA.

## New boundary statements to ADD at Phase 6C
- Donor-isolation description for flooded variants (protocol + ledger reference).
- Threshold-transfer protocol description (inner family-grouped OOF; FPR reporting).
- Compound M3+F200 result (whatever v2 shows).
- Secondary-control (benign_general) FPR/score table at frozen v2 thresholds.
