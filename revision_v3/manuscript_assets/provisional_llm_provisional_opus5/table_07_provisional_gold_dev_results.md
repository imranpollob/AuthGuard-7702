**PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE. LABEL_SOURCE=LLM_PROVISIONAL_OPUS5. STATIC_ANALYZER_EVIDENCE=VISIBLE. STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW.**

# Table 7 — Provisional Gold-Dev Results

n_evaluated_binary=49, uncertain_coverage=18.3%

| Model | AUPRC | AUROC | Precision | Recall | Specificity | FPR | F1 | Balanced Acc | Brier | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| authguard_sequence_dense | 0.920 | 0.726 | 0.941 | 0.410 | 0.900 | 0.100 | 0.571 | 0.655 | 0.438 | 0.487 |
| authguard_reference_v3 | 0.919 | 0.723 | 0.941 | 0.410 | 0.900 | 0.100 | 0.571 | 0.655 | 0.447 | 0.483 |
| flat_cnn_matched_16384 | 0.932 | 0.759 | 0.941 | 0.410 | 0.900 | 0.100 | 0.571 | 0.655 | 0.428 | 0.472 |
| flat_cnn_16384 | 0.943 | 0.815 | 0.941 | 0.410 | 0.900 | 0.100 | 0.571 | 0.655 | 0.423 | 0.468 |
| source_static_rule | - | - | 0.941 | 0.410 | 0.900 | 0.100 | 0.571 | 0.655 | - | - |
