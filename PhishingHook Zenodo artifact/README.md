# PhishingHook

The `phishinghook.zip` archive contains modules for extracting, disassembling, and analyzing Ethereum smart contracts bytecode. It is the implementation of the paper: "PhishingHook: Catching Phishing Ethereum Smart Contracts leveraging EVM Opcodes."

In addition to the core modules, it includes a `cli/` directory that provides a command-line interface (CLI). The CLI comes with a runnable example to disassemble EVM bytecodes and detect whether a smart contract is phishing or benign.

## Modules

### Bytecode Disassembler Module

This module contains code for disassembling Ethereum Virtual Machine (EVM) bytecode. It uses a modified version of the  [evmdasm](https://github.com/tintinweb/evmdasm) library up-to-date with the Shangai fork.

- `evmdasm/evmdasm/disassembler.py`: Contains the `EvmDisassembler` class for disassembling EVM bytecode.
- `evmdasm/evmdasm/registry.py`: Contains the registry of EVM instructions.
- `opcode_from_bytecode.py`: Script to decode bytecodes and save the opcodes to a CSV file.

### Bytecode Extraction Module

This module contains scripts for extracting bytecode from Ethereum smart contract addresses.

- `bytecode_from_hash.py`: Script to fetch bytecode from Ethereum addresses using the Etherscan API.

### Dataset

This directory contains the datasets used in the paper.

- `bytecodes/`: Raw bytecodes of the smart contracts, divided in benign and phishing (pre and post deduplication).
- `contracts/`: Hashes of the smart contracts, divided in benign and phishing (pre and post deduplication).
- `disassembled_unique_bytecodes.zip`: Bytecodes disassembled in their sequence of opcodes, in the form (Mnemonic, Operand, Gas).

### Model Evaluation Module

This module contains code for evaluating the models presented in the paper.

- `models/`: Contains the model implementations.
  - `histogram_similarity_classifiers/`: Contains histogram similarity classifier implementations and the results presented in the paper.
  - `language_models/`: Contains language model implementations (SCSGuard, GPT-2 and T5) and the results presented in the paper.
  - `vision_models/`: Contains vision model implementations (ViT+R2D2, ViT+Freq and ECA+EfficientNet,) and the results presented in the paper.
  - `vulnerability_detection_models/`: Contains the ESCORT model for vulnerability detection and the results presented in the paper.
- `scalability/`: Contains the results of the scalability analysis and the code for the Critical Difference Diagram.
- `time_resistance/`: Contains datasets, results and code of the time resistance analysis.
- `utils/`: Contains utility scripts.

### Post-Hoc Analysis Module

This module contains scripts and data (in R) for post hoc analysis.

- `kruskal_wallis_results.csv`: Contains Kruskal-Wallis test results.
- `kruskal_wallis.R`: Script to perform Shapiro-Wilk, Kruskal-Wallis and Dunn's tests.
- `non_normal_metrics.csv`: Contains metrics that failed the Shapiro-Wilk test.
- `results.csv`: Contains the evaluation results from the paper.
- `shapiro_wilk_test_results.csv`: Contains Shapiro-Wilk test results.

## Installation

The Python version used by PhishingHook is 3.10.12, the R version is 4.4.2.
To install the required Python libraries (on UNIX-like systems), use the following commands:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
The `requirements.txt` file contains as well the R dependencies used in the post hoc analysis, that have to be installed manually by the user.
