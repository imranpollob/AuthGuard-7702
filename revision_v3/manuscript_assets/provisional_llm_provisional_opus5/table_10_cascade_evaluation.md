**PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE. LABEL_SOURCE=LLM_PROVISIONAL_OPUS5. STATIC_ANALYZER_EVIDENCE=VISIBLE. STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW.**

# Table 10 — Cascade Evaluation (Gold-Test, frozen policy from Gold-Dev)

escalation band (from Gold-Dev): {'low': 0.053608263272016, 'high': 0.5092610677561413}

| Policy | % Escalated | % Resolved Locally | Recall (UNSAFE coverage) | FNR | FPR |
|---|---|---|---|---|---|
| A_authguard_alone | 0.0% | 100.0% | 0.426 | 0.574 | 0.200 |
| B_static_rule_alone | 0.0% | 100.0% | 0.426 | 0.574 | 0.150 |
| C_authguard_first_rule_escalation | 21.9% | 78.1% | 0.426 | 0.574 | 0.150 |
| D_rule_first_authguard_escalation | 38.3% | 61.7% | 0.417 | 0.583 | 0.150 |
| E_uncertainty_triggered_escalation | 14.7% | - | - | - | - |
