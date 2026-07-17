# Phase 0 Failures and Deviations

The original macOS ARM64 harness validation passed exactly. On the resumed Linux x86_64 host,
matched-library XGBoost histogram fits are deterministic but differ from the frozen ARM scores
by up to 0.022 (AuthGuard) and 0.055 (opcode XGBoost), failing the 1e-6 cross-platform tolerance.
The platform-specific records and within-host comparison policy are documented in
`revision_v2/audits/cross_platform_validation.md`. No frozen result was overwritten.

Finalization also found one stale entry in `protocols.sha256`: the donor-isolation file was
committed as v1.1 before donor-isolated results, but the Phase-0 ledger retained the v1.0 hash.
Four other entries verify. Neither immutable artifact was rewritten; see
`revision_v2/audits/protocol_hash_validation.md`.
