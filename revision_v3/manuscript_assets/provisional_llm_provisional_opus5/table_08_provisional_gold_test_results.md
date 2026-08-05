**PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE. LABEL_SOURCE=LLM_PROVISIONAL_OPUS5. STATIC_ANALYZER_EVIDENCE=VISIBLE. STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW.**

# Table 8 — Provisional Gold-Test Results

n_evaluated_binary=128, uncertainty_exclusion_rate=14.7%

| Model | AUPRC | 95% CI | AUROC | Recall | FPR | F1 | Balanced Acc |
|---|---|---|---|---|---|---|---|
| flat_cnn_16384 | 0.926 | [0.864, 0.972] | 0.710 | 0.435 | 0.200 | 0.591 | 0.618 |
| flat_cnn_matched_16384 | 0.916 | [0.849, 0.967] | 0.671 | 0.435 | 0.200 | 0.591 | 0.618 |
| authguard_sequence_dense | 0.915 | [0.850, 0.965] | 0.659 | 0.426 | 0.200 | 0.582 | 0.613 |
| authguard_reference_v3 | 0.911 | [0.842, 0.963] | 0.648 | 0.435 | 0.200 | 0.591 | 0.618 |
| provisional_final_model | 0.909 | [0.833, 0.970] | 0.676 | 0.972 | 0.950 | 0.905 | 0.511 |
| source_static_rule | - | - | - | 0.426 | 0.150 | 0.586 | 0.638 |
