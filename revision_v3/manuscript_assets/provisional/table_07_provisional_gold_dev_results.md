**PROVISIONAL — LLM REFERENCE LABELS. LABEL_SOURCE=LLM_PROVISIONAL. STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS.**

# Table 7 — Provisional Gold-Dev Results

n_evaluated_binary=47, uncertain_coverage=21.7%

| Model | AUPRC | AUROC | Precision | Recall | Specificity | FPR | F1 | Balanced Acc | Brier | ECE |
|---|---|---|---|---|---|---|---|---|---|---|
| authguard_sequence_dense | 0.925 | 0.610 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.549 | 0.601 |
| authguard_reference_v3 | 0.923 | 0.571 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.559 | 0.578 |
| flat_cnn_matched_16384 | 0.922 | 0.614 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.559 | 0.588 |
| flat_cnn_16384 | 0.930 | 0.657 | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | 0.555 | 0.586 |
| source_static_rule | - | - | 0.882 | 0.357 | 0.600 | 0.400 | 0.508 | 0.479 | - | - |
