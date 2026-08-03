**PROVISIONAL — OPUS 5 LABELS WITH STATIC-ANALYZER EVIDENCE. LABEL_SOURCE=LLM_PROVISIONAL_OPUS5. STATIC_ANALYZER_EVIDENCE=VISIBLE. STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW.**

# Table 6 — Deployment Evaluation

Hardware: NVIDIA GeForce RTX 2080 SUPER, x86_64, torch 2.9.0+cu128

| Model | Device | Params | Forward p50 (ms) | Forward p99 (ms) | E2E p50 (ms) | Throughput (items/s) |
|---|---|---|---|---|---|---|
| authguard_sequence_dense | cpu | 97,646 | 2.83 | 3.44 | 2.72 | 125.7 |
| authguard_sequence_dense | cuda | 97,646 | 3.50 | 4.04 | 3.43 | 116.7 |
| authguard_sequence_dense | onnx-cpu | - | 4.99 | 8.31 | - | - |
| authguard_reference_v3 | cpu | 38,562 | 1.07 | 1.36 | 1.07 | 432.0 |
| authguard_reference_v3 | cuda | 38,562 | 1.18 | 1.81 | 1.20 | 411.2 |
| authguard_reference_v3 | onnx-cpu | - | nan | nan | - | - |
