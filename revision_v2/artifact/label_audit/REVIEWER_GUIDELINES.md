# Reviewer Guidelines — EIP-7702 Delegate Bytecode Adjudication

You receive anonymized evidence packets (structural bytecode signals + a model risk score;
addresses/chains withheld). For each anon_id record in your BLINDED form:

- label: one of `malicious`, `benign`, `uncertain`.
  - malicious: the bytecode's capability profile is consistent with unauthorized asset
    movement or account takeover if authorized as an EIP-7702 delegate.
  - benign: capability profile consistent with legitimate account-abstraction / wallet logic.
  - uncertain: bytecode alone is insufficient (e.g., delegation pointer, minimal proxy,
    storage-gated logic whose behavior depends on external state).
- confidence: high | medium | low.
- rationale: one sentence.

Do NOT look up addresses. Judge from the packet only. The model risk score is provided for
context; you may disagree with it. Work independently; do not confer with other reviewers.
