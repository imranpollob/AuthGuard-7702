**PROVISIONAL — LLM REFERENCE LABELS. LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

# Table 8 — Provisional Gold-Test Results

n_evaluated_binary=138, uncertainty_exclusion_rate=8.0%

| Model | AUPRC | 95% CI | AUROC | Recall | FPR | F1 | Balanced Acc |
|---|---|---|---|---|---|---|---|
| provisional_final_model | 0.968 | [0.915, 0.999] | 0.756 | 1.000 | 0.857 | 0.978 | 0.571 |
| flat_cnn_16384 | 0.965 | [0.928, 0.993] | 0.599 | 0.351 | 0.429 | 0.511 | 0.461 |
| authguard_sequence_dense | 0.963 | [0.928, 0.991] | 0.537 | 0.336 | 0.429 | 0.494 | 0.454 |
| flat_cnn_matched_16384 | 0.962 | [0.923, 0.991] | 0.546 | 0.351 | 0.429 | 0.511 | 0.461 |
| authguard_reference_v3 | 0.959 | [0.919, 0.990] | 0.513 | 0.344 | 0.429 | 0.503 | 0.457 |
| source_static_rule | - | - | - | 0.344 | 0.143 | 0.508 | 0.600 |
