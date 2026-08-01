**PROVISIONAL — LLM REFERENCE LABELS. LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

# Table 10 — Cascade Evaluation (Gold-Test, frozen policy from Gold-Dev)

escalation band (from Gold-Dev): {'low': 0.0442239707466991, 'high': 0.5810097223694125}

| Policy | % Escalated | % Resolved Locally | Recall (UNSAFE coverage) | FNR | FPR |
|---|---|---|---|---|---|
| A_authguard_alone | 0.0% | 100.0% | 0.336 | 0.664 | 0.429 |
| B_static_rule_alone | 0.0% | 100.0% | 0.344 | 0.656 | 0.143 |
| C_authguard_first_rule_escalation | 37.0% | 63.0% | 0.344 | 0.656 | 0.143 |
| D_rule_first_authguard_escalation | 33.3% | 66.7% | 0.336 | 0.664 | 0.143 |
| E_uncertainty_triggered_escalation | 8.0% | - | - | - | - |
