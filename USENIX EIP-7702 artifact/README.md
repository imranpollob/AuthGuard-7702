# EIP-7702 Malicious Contract Detection Tool

This repository contains the source code and intermediate results for detecting malicious smart contracts targeting EIP-7702 smart accounts.  
The detection framework contains three pipelines for corresponding attack categories**:

1. **EOA-targeted attacks** – malicious contracts aiming at externally owned accounts.
2. **CA-targeted attacks** – malicious contracts aiming at vulnerable smart contracts.
3. **Composite attacks** – combined scenarios aiming at both EOAs and CAs.


---

## 📂 Repository Structure

| File / Folder | Description |
|---------------|-------------|
| `get_code/` | Scripts to fetch contract bytecode from blockchain explorers (e.g., Etherscan API). This is the first stage of all three detection pipelines. |
| `decompile/` | Main detection entry point. Loads decompiled results and applies detection rules for EOA-targeted, CA-targeted, or composite attacks. |
| `decompile/crosscontract_sh/` | Scripts for cross-contract analysis, enabling the detection of multi-contract attack patterns. |
| `contracts_with_bytecode.xlsx` | Intermediate dataset containing all addresses with successfully retrieved bytecode. Can be used to skip the `get_code/` step. |
| `output_#.zip` | Archived intermediate dataset for #-targeted detection. Contains detected malicious contract reports and logs. Can be used to skip the `get_code/` step. |
| `AM_Detect_FlashloanCall.jsonl` | Intermediate detection output for suspicious flash loan calls observed in EOA-targeted or composite attacks. Can be used to skip the `decompile/` step. |
| `AM_FunctionSelector.jsonl` | Intermediate detection output for mapping between function selectors and their decompiled semantics, used for identifying malicious function patterns. Can be used to skip the `decompile/` step. |
| `result.jsonl result.xlsx` | Detection result. |
| `analysis_information/` | Finding related dataset, including obfuscated vulnerable contract code example and malicious smart account addresses. |

---

## Reproduction Guide

The pipeline supports **restarting from any intermediate stage** using the saved files we mentioned before.

### **Full Pipeline**
```bash
# Example: ca_detect

# Step 1: Retrieve bytecode, you may need to change file path, and use a valid API key
python ./ca_detect/main.py
python ./ca_detect/get_code.py


# Step 2: Decompile with Gigahorse, https://github.com/nevillegrech/gigahorse-toolchain#

mv ca_detect/decompile/main.py ./gigahorse
mv ca_detect/decompile/env.yaml ./gigahorse
mv ca_detect/decompile/run_analysis.sh ./gigahorse
mv ca_detect/decompile/analyze.dl ./gigahorse/clients


# Step 3: Run main detection
python ./gigahorse/main.py

mv ca_detect/decompile/AM_Detect_FlashloanCall.jsonl ./ca_detect/decompile/crosscontract_sh
mv ca_detect/decompile/AM_FunctionSelector.jsonl ./ca_detect/decompile/crosscontract_sh
python ./ca_detect/decompile/crosscontract_sh/cross_match.py
```

---

### **2. Starting from Bytecode or Decompiled Results**
```bash
# Starting from Bytecode

mv ca_detect/decompile/main.py ./gigahorse
mv ca_detect/decompile/env.yaml ./gigahorse
mv ca_detect/decompile/run_analysis.sh ./gigahorse
mv ca_detect/decompile/analyze.dl ./gigahorse/clients
python ./gigahorse/main.py


# Starting from Decompiled Results

python ./ca_detect/decompile/crosscontract_sh/cross_match.py
```


---

## Dependencies

- **Python3** 
- **Gigahorse Decompiler** (Source Code Deployment)
- **API access to blockchain explorers** (Etherscan, Infura)  


---

## Notes
- **Intermediate files** are intentionally preserved to allow partial pipeline execution without re-fetching or re-decompiling contracts.
- The cross-contract analysis stage is critical for detecting ca and composite attacks involving multiple interacting contracts. 
- If the python file do not works, check the path and .env file, making sure all APIs and file paths are correct. 

## Ethics Statement
This research is conducted solely for academic and security purposes.
All detection tools, experiments, and released datasets are designed only to identify attacker-controlled smart contracts associated with EIP-7702 malicious activities.

**No victim identification** – This dataset does not and cannot reveal the identities of victim addresses, ensuring that no sensitive or private user data is exposed.

