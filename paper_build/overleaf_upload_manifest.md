# Overleaf Upload Manifest

Upload directory: `paper_build/overleaf/`

Upload all 13 files while preserving their relative directory structure. Total payload: **308,609 bytes**. All manuscript sections, tables, captions, and the TikZ architecture are embedded directly in `main.tex`; it contains no `\input` command.

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
| `main.tex` | 53484 | Complete IEEEtran manuscript, including all sections/tables/TikZ | Yes | `5e3220819a2c7592716c7f50ce58dd150cb4879a320999ef3947804a3d0345c0` |
| `references.bib` | 7030 | Used bibliography entries | Yes | `375bccf49d7b6fc51baca8e5a24ea7ae2c6e0b923f0ac0289927b54391b8ab4f` |

## Upload checks

- Main document: `main.tex`.
- Direct compilation inputs beyond `main.tex`: `references.bib` and the three PDF figures.
- The generation scripts and JSON files are not executed by Overleaf and are not compilation dependencies; the prebuilt vector PDFs are authoritative figure inputs.
- No section, table, or TikZ source file is external to `main.tex`.
- No custom class/style file is bundled. Overleaf must supply the standard `IEEEtran` class and listed standard packages.
- Hashes should be regenerated if any file changes during the Overleaf reduction pass.
