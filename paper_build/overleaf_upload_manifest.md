# Overleaf Upload Manifest

Upload directory: `paper_build/overleaf/`

Upload all 27 files while preserving their relative directory structure. Total payload: **309,051 bytes**. The `Required` column indicates whether LaTeX/BibTeX directly needs the file for the paper build; reproducibility files must still be uploaded as part of the requested complete package.

| Relative path | Bytes | Role | Required | SHA-256 |
|---|---:|---|---|---|
| `README.md` | 733 | Anonymous build instructions | No | `db70efa20f568ec1ab38eefaf5076a80621cbc5067d7c172eda41f06f6b3781c` |
| `figure_data/task_aligned_advtrain_results.json` | 131286 | G-ADV figure source data | Reproducibility | `3e030136dedca890558698939d06f47e8d0f5fa8026b9641bc85bdf101fe7106` |
| `figure_data/task_aligned_detection_results.json` | 49734 | G-DET figure source data | Reproducibility | `38a812ce13b81516811d43607edff2d291516193e2410966f403f9a60ef77520` |
| `figure_data/task_aligned_mutation_curve.json` | 5250 | G-MUT figure source data | Reproducibility | `45a76cf8babc74a3b3554446daefcf4c3f5c957a3f0cc614201f1c77dfc1da47` |
| `figure_data/task_aligned_mutation_volume.json` | 4081 | G-VOL figure source data | Reproducibility | `ae7984fbab0d4462978c298cd80b64ab852a929c4ab55f24d52ebe215d8cb0fd` |
| `figures/advtrain_heldout.pdf` | 14526 | G-ADV vector figure | Yes | `8f14cc6253d84d620ee607573eda8cd6f8c52a2399cf1edf0c4ca488a013d030` |
| `figures/generate_advtrain_heldout.py` | 3092 | G-ADV figure generator | Reproducibility | `01c6541786557859517243e1e9157f54143e8dbccb7505539d8640382bd9c4a7` |
| `figures/generate_mutation_and_flooding.py` | 3851 | G-MUT/G-VOL figure generator | Reproducibility | `806434e0de99be17fcb21dc75bc8d2411bf39f964e003a3bef5b8b53d8ac75b3` |
| `figures/generate_random_vs_family.py` | 2855 | G-DET split figure generator | Reproducibility | `0919614ed404f52ef868c06047dfb6a5c20fc30ed40c3a67a42df2ac6bb17c41` |
| `figures/mutation_and_flooding.pdf` | 18398 | G-MUT/G-VOL vector figure | Yes | `5385f86f6cabe6a0d991dd41007b63f44edaaaa1acdf2194ac87c7ec47e3351a` |
| `figures/random_vs_family.pdf` | 14289 | G-DET split vector figure | Yes | `97ea8cc8f18092eb6b6ef0189ecb9a2572e66da8fcd5cb8176c4c7bb9063b33a` |
| `figures/system_architecture.tex` | 2947 | Stacked TikZ architecture | Yes | `90b4cf4bb04d258b173cd4d39569ab7f14f6068aff900e9c3942c1d76270eb29` |
| `main.tex` | 716 | IEEEtran main driver | Yes | `9dff3ad6bb0bcdf36608ac0f9297bd96828172d9b38392e580d41753b83e627c` |
| `references.bib` | 7030 | Used bibliography entries | Yes | `375bccf49d7b6fc51baca8e5a24ea7ae2c6e0b923f0ac0289927b54391b8ab4f` |
| `sections/abstract.tex` | 1586 | Abstract and index terms | Yes | `20c331fab8f938646fcc3580eb3ef1b92285957bd948c73e5dd058a13c69e1dc` |
| `sections/background_related.tex` | 6683 | Background and Related Work | Yes | `746795934f69521edc3b057bfe4dd52700f9e41dd4cc9a0120c7dc1b6b4f0ac0` |
| `sections/conclusion.tex` | 1158 | Conclusion | Yes | `962db5eef23ecdb4c6bd2a86c322133d1ebecec6e1d7aabf8791bf392f2447c8` |
| `sections/discussion.tex` | 6264 | Discussion and Limitations | Yes | `12ef53b5c45ec1a820ba7e969a4917e44ee35bb390737ee3e22d0d0e06dc0b20` |
| `sections/evaluation.tex` | 8255 | Evaluation | Yes | `3681cb37bf4234ae24d02fc9ba55ed5675c33ccb2632a1383163300d2fca48dd` |
| `sections/introduction.tex` | 5597 | Introduction | Yes | `16bfaa97e798687d1821428f8f835e2457956134956c5311a799bffde9b7bd08` |
| `sections/methodology.tex` | 6840 | Dataset and Methodology | Yes | `105652e034a3a3a304f736f2cc568177093c069e63a7fa1529a250a702dc464b` |
| `sections/problem_threat.tex` | 3415 | Problem and Threat Model | Yes | `e50dbacf4e53aa4f3723a17cde626fdc93c3dc0120e61b2a30e7231795b9230a` |
| `sections/system_design.tex` | 5880 | AuthGuard-7702 Design | Yes | `73efbbf7e490826247743cfd2caa1d9d139012ad0d04c071107d857d47f4c141` |
| `tables/dataset_composition.tex` | 1049 | Table I | Yes | `1acf7942fc7a9ee2180017b7b579aa50be85a7da2667eea1f648654ac417bc15` |
| `tables/gadv_results.tex` | 1507 | G-ADV table | Yes | `786ff734a41f67fc5747f62076978626fab68ab9e8cb3f14231225ff71d58360` |
| `tables/gdet_performance.tex` | 1143 | G-DET table | Yes | `941207b19af58f0d06e2712ce6d346d2a1ac0d919ce2123ddf00404e41c1f7da` |
| `tables/gmut_robustness.tex` | 886 | G-MUT table | Yes | `d6936b1fca15de94394cce60c4a3fc43e993084b30e1c63ff30299e891b0e356` |

## Upload checks

- Main document: `main.tex`.
- Expected direct inputs: 9 section files, 4 table files, 1 TikZ figure source, 3 PDF figures, and `references.bib`.
- The generation scripts and JSON files are not executed by Overleaf and are not compilation dependencies; the prebuilt vector PDFs are authoritative figure inputs.
- No custom class/style file is bundled. Overleaf must supply the standard `IEEEtran` class and listed standard packages.
- Hashes should be regenerated if any file is changed during the Overleaf reduction pass.
