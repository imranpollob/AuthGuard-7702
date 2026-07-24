# AuthGuard-MSP confirmation decision

All decisions use only outer test folds 1--4. Fold 0 is development-only.

| Condition | Metric | Comparator | Delta | 95% CI | Decision |
|---|---|---|---:|---:|---|
| M0 | AUPRC | chunk_attention_control_16384 | -0.0069 | [-0.0240, +0.0114] | INCONCLUSIVE |
| M0 | Recall_05 | chunk_attention_control_16384 | +0.0373 | [+0.0123, +0.0585] | SUPPORTED |
| M0 | AUPRC | flat_control_16384 | +0.0033 | [-0.0098, +0.0167] | INCONCLUSIVE |
| M0 | Recall_05 | flat_control_16384 | +0.0505 | [+0.0215, +0.0830] | SUPPORTED |
| M0 | AUPRC | authguard_reference_16384 | +0.0179 | [-0.0078, +0.0504] | INCONCLUSIVE |
| M0 | Recall_05 | authguard_reference_16384 | +0.0166 | [-0.0035, +0.0417] | INCONCLUSIVE |
| F200 | AUPRC | chunk_attention_control_16384 | -0.1074 | [-0.1455, -0.0730] | NOT SUPPORTED |
| F200 | Recall_05 | chunk_attention_control_16384 | -0.2109 | [-0.2548, -0.1648] | NOT SUPPORTED |
| F200 | AUPRC | flat_control_16384 | +0.0260 | [+0.0041, +0.0530] | SUPPORTED |
| F200 | Recall_05 | flat_control_16384 | +0.1524 | [+0.1202, +0.1889] | SUPPORTED |
| F200 | AUPRC | authguard_reference_16384 | -0.0798 | [-0.1097, -0.0451] | NOT SUPPORTED |
| F200 | Recall_05 | authguard_reference_16384 | -0.1795 | [-0.2278, -0.1219] | NOT SUPPORTED |

The primary novelty decision is clean AUPRC versus the 16K attention control.
Superiority over the 16K flat control is required for a predictive hierarchy claim.
