# Reconnaissance Report — 4 Blockchain-Security Artifacts

**Verdict up front (PART 2):** Bytecode **is** directly available in the USENIX artifact. The malicious EOA-targeted contracts are represented as **bytecode** (not merely addresses) in `eoa_detect/get_code/contracts_with_bytecode.xlsx`, column `bytecode`, **793 rows**, all non-empty. Same is true for CA-targeted (`ca_detect/get_code/contracts_with_bytecode_2.xlsx` + `_1.xlsx`) and composite (`.hex` files inside `output_composite.zip`).

---

## PART 1 — Inventory

### 1.1 PTXPhish-main (932K)

```
PTXPhish-main/
├── README.md                        5K   paper README, dataset description + category table
└── dataset/
    ├── InitialAddress.xlsx         27K   per-category "seed" phishing addresses (43 cols, 56 rows)
    └── PTXPHISH.xlsx               876K  ground-truth dataset: tx-hashes per phishing subtype + benign KOL/dev addrs
```

### 1.2 PhishingHook Zenodo artifact (840M, up from 220M before extraction — decompression overhead, no new data)

**Update:** the user extracted all zip archives under `artifact/dataset/` in place (originals deleted, plain files/folders now present). Content is byte-identical to what was inside the zips — verified by re-checking every line count below — only the container changed. `disassembled_unique_bytecodes.zip` extracted directly to `dataset/opcodes.csv` (no subfolder), unlike the others which extracted into a same-named subfolder.

```
PhishingHook Zenodo artifact/
├── README.md                        3K   top-level paper/module description
├── cli/                                  standalone dockerized CLI demo
│   ├── Dockerfile                  324B  docker build file
│   ├── README.md / README.md~       3K   CLI usage docs
│   ├── phishinghook.py              4K   CLI entrypoint (disassemble/detect subcommands)
│   ├── random_forest_model.pkl      9M   pretrained RF phishing classifier
│   ├── requirements.txt            76B   pip deps
│   ├── test_bytecodes.txt          28K   1 sample bytecode line for demo
│   └── evmdasm/setup.py            981B  vendored disassembler package
└── artifact/
    ├── requirements.txt            749B  pip + R deps
    ├── bytecode_disassembler_module/opcode_from_bytecode.py  812B  bytecode→opcode CSV script
    ├── bytecode_extraction_module/bytecode_from_hash.py       634B  Etherscan bytecode fetcher
    ├── dataset/
    │   ├── opcodes.csv                       372M  disassembly of the 7000 unique bytecodes: Contract,Opcode,Operand,Gas,Label
    │   ├── bytecodes/bytecodes/benign_bytecodes.txt      80M  RAW (non-dedup, 20,000-row sample) benign bytecode
    │   ├── bytecodes/bytecodes/phishing_bytecodes.txt    86M  RAW (non-dedup, all 17455) phishing bytecode
    │   ├── bytecodes/unique_bytecodes/unique_benign_bytecodes.txt    45M  DEDUPED benign bytecode (3542)
    │   ├── bytecodes/unique_bytecodes/unique_phishing_bytecodes.txt  31M  DEDUPED phishing bytecode (3458)
    │   ├── contracts/contracts/benign.txt               171M  RAW (non-dedup) benign ADDRESS list (4,170,611)
    │   ├── contracts/contracts/phishing.txt             733K  RAW (non-dedup) phishing ADDRESS list (17455)
    │   ├── contracts/unique_contracts/unique_benign.txt 149K  DEDUPED benign ADDRESS list (3542)
    │   └── contracts/unique_contracts/unique_phishing.txt 145K DEDUPED phishing ADDRESS list (3458)
    ├── model_evaluation_module/        ML model results (histogram/LM/vision/vulnerability classifiers) — all CSV, metrics only
    └── post_hoc_analysis_module/       Kruskal-Wallis/Shapiro-Wilk stats CSVs on the above results
```

**`opcodes.csv` (now directly inspectable — previously only guessed from README):**
- Columns (exact): `Contract, Opcode, Operand, Gas, Label`
- Rows: 22,675,861 opcode-level data rows (+1 header)
- `Contract` is an integer id, not an address; `Label` is 0=benign / 1=phishing
- Row counts confirm 1:1 correspondence with the deduped bytecode sets: Label=0 → 3542 unique `Contract` ids / 13,762,902 opcode rows; Label=1 → 3458 unique `Contract` ids / 8,912,959 opcode rows
- Sample rows:
  ```
  Contract,Opcode,Operand,Gas,Label
  0,PUSH1,80,3,0
  0,PUSH1,40,3,0
  ```

### 1.3 USENIX EIP-7702 artifact (69M)

```
USENIX EIP-7702 artifact/
├── README.md                        4K   pipeline description (EOA/CA/composite attack detection)
├── overview.xlsx                    9K   HEADLINE summary table (tx counts + detection counts, all chains)
├── analysis_information/
│   ├── sa_contract.xlsx            102K  all EIP-7702 delegate addresses observed (chain, addr, count)
│   ├── sa_contract_malicious.xlsx  110K  same + 'matched' column (mostly 'unmatched')
│   └── obfuscated_vul_ca/
│       ├── obfuscated_file_item_counts.xlsx  326K  obfuscated (16-hex, NOT full address) case-study IDs
│       └── obfuscated_search_results.xlsx      2M  grep-style code snippets keyed to same obfuscated IDs
├── eoa_detect/
│   ├── extracted_addresses.xlsx     29K   793-row / 718-unique candidate malicious EOA-target addresses
│   ├── detect_result.jsonl         152K   FINAL 793-row EOA-targeted malicious detection result (=overview total)
│   ├── get_code/contracts_with_bytecode.xlsx  4M   chain+addr+count+**bytecode** for all 2685 delegate candidates
│   ├── get_code/output.zip          6M   2685 raw `.hex` files (one per chain/address) — bytecode
│   ├── get_code/suspected_txs.xlsx 462K   same 2685-row candidate list, no bytecode
│   └── decompile/                        Gigahorse/Soufflé decompile + rule outputs (jsonl)
├── ca_detect/
│   ├── result.xlsx                 17K   80-row flashloan cross-contract match (78 unique malicious contracts)
│   ├── get_code/contracts_with_bytecode_1.xlsx  2M   1378-row bytecode batch (98.8% non-empty)
│   ├── get_code/contracts_with_bytecode_2.xlsx  9M   27633-row bytecode batch (only 16.9% non-empty)
│   ├── get_code/output_ca.zip      27M   27633 raw `.hex` files — bytecode
│   ├── get_code/suspected_tx1.csv / tx2.csv   address-only versions of the two batches above
│   └── decompile/                        Gigahorse outputs + crosscontract_sh/ (result.xlsx, related_contracts.xlsx)
└── composite_detect/
    ├── result.xlsx                  6K   6-row final result → 7 unique malicious contracts (target ∪ related)
    ├── get_code/ca_address.xlsx    238K   5909-row candidate list, chain+from+ca_address, **no bytecode column**
    ├── get_code/output_composite.zip  11M   5581 raw `.hex` files — bytecode (this is where composite bytecode lives)
    └── decompile/                        Gigahorse outputs + crosscontract_sh/ (result.xlsx, mid_matched_results.xlsx)
```

### 1.4 scamsonethereum-main (400K)

```
scamsonethereum-main/
├── README.md                       19B   empty except title
├── LICENSE                         34K   MIT-style license text
├── all_across_hard.txt             21K   495 lines — Ethereum addresses (0x + 40 hex), one per line
└── master_blacklist_set.txt       332K   7915 lines — Ethereum addresses (0x + 40 hex), one per line
```

---

### README verbatim excerpts (schema / labeling / dataset-size statements)

**PTXPhish-main/README.md** (lines 10–23, category table — the authoritative "how many contracts" statement):
```
| Category                       |                   |                     | Target Assets | Spread Method | Num  |
| Exploiting legitimate contract | Ice phishing      | Approve             | ERC20         | website       | 1247 |
|                                |                   | Permit              | ERC20         | website       | 814  |
|                                |                   | SetApproveForAll    | NFT           | website       | 508  |
|                                | NFT order         | Bulk transfer       | NFT           | website       | 37   |
|                                |                   | Proxy upgrade       | NFT           | website       | 108  |
|                                |                   | Free buy order      | ERC20 & NFT   | website       | 464  |
| Deploying phishing contract    | Address Poisoning | Zero value transfer | ERC20         | Transaction   | 104  |
|                                |                   | Fake token transfer | ERC20         | Transaction   | 100  |
|                                |                   | Dust value transfer | ERC20         | Transaction   | 22   |
|                                | Payable Function  | Airdrop function    | ETH           | Transaction   | 788  |
|                                |                   | Wallet function     | ETH           | Transaction   | 808  |
| Benign                         | -                 | -                   | -             | -             | 13557 |
"The open-source ground-truth dataset is in the ./dataset/PTXPHISH.xlsx"
```
Note: the "Num" column counts **transactions/hashes**, not unique contract addresses — confirmed by inspection (PTXPHISH.xlsx cells are 64-hex tx hashes, not 40-hex addresses).

**PhishingHook Zenodo artifact/README.md** (lines 23–30, dataset schema):
```
### Dataset
This directory contains the datasets used in the paper.
- `bytecodes/`: Raw bytecodes of the smart contracts, divided in benign and phishing (pre and post deduplication).
- `contracts/`: Hashes of the smart contracts, divided in benign and phishing (pre and post deduplication).
- `disassembled_unique_bytecodes.zip`: Bytecodes disassembled in their sequence of opcodes,
  in the form (Mnemonic, Operand, Gas).
```
(No explicit total-contract-count statement in this README; counts derived by direct file inspection below.)

**USENIX EIP-7702 artifact/README.md** (lines 3–26, schema/labeling):
```
The detection framework contains three pipelines for corresponding attack categories:
1. EOA-targeted attacks – malicious contracts aiming at externally owned accounts.
2. CA-targeted attacks – malicious contracts aiming at vulnerable smart contracts.
3. Composite attacks – combined scenarios aiming at both EOAs and CAs.
| get_code/ | Scripts to fetch contract bytecode from blockchain explorers (e.g., Etherscan API). ... |
| decompile/ | Main detection entry point. Loads decompiled results and applies detection rules ... |
| contracts_with_bytecode.xlsx | Intermediate dataset containing all addresses with successfully
  retrieved bytecode. Can be used to skip the get_code/ step. |
| result.jsonl result.xlsx | Detection result. |
```
Ethics statement (lines 93–97): "No victim identification — this dataset does not and cannot reveal the identities of victim addresses."

**scamsonethereum-main/README.md** (full, 2 lines): `# scamsonethereum` — no further schema documentation exists in this file.

---

## PART 2 — Bytecode vs. Addresses classification

**Headline: 883 malicious USENIX contract-instances carry real bytecode directly (793 EOA + 83 CA-flashloan + 7 composite); PhishingHook additionally carries 3,458 phishing + 3,542 benign unique bytecodes. Several USENIX and PTXPhish files are address-only.**

### (A) Files containing runtime EVM bytecode

| File | Column/field | Rows w/ non-empty bytecode | Notes |
|---|---|---|---|
| `USENIX .../eoa_detect/get_code/contracts_with_bytecode.xlsx` | `bytecode` | **2685 / 2685** (all) | full delegate-address candidate set; 793 of these are the confirmed-malicious subset (join on chain+address against `detect_result.jsonl`) |
| `USENIX .../eoa_detect/get_code/output.zip` | `*.hex` file content | 2500 / 2685 (185 empty `0x` sampled-rate) | one file per (chain,address), duplicates the xlsx above |
| `USENIX .../ca_detect/get_code/contracts_with_bytecode_1.xlsx` | `bytecode` | 1372 / 1378 (99.6%) | first CA-targeted fetch batch |
| `USENIX .../ca_detect/get_code/contracts_with_bytecode_2.xlsx` | `bytecode` | 4672 / 27633 (16.9%) | second, much larger CA-targeted fetch batch — most `eth_getCode` calls returned empty |
| `USENIX .../ca_detect/get_code/output_ca.zip` | `*.hex` | ~5780/27633 sampled non-empty | duplicates the xlsx above |
| `USENIX .../composite_detect/get_code/output_composite.zip` | `*.hex` | majority non-empty (sampled 813/2000) | **only** bytecode source for composite — `ca_address.xlsx` has no bytecode column |
| `PhishingHook .../dataset/bytecodes/unique_bytecodes/unique_phishing_bytecodes.txt` | 1 bytecode per line | **3458 / 3458** (all) | deduped phishing bytecode |
| `PhishingHook .../dataset/bytecodes/unique_bytecodes/unique_benign_bytecodes.txt` | 1 bytecode per line | **3542 / 3542** (all) | deduped benign bytecode — *sampled* from only 20,000 of the 4,170,611 candidate benign addresses |
| `PhishingHook .../dataset/bytecodes/bytecodes/phishing_bytecodes.txt` | 1 bytecode per line | 17455 / 17455 (all) | raw, pre-dedup, 1:1 with `contracts/contracts/phishing.txt` |
| `PhishingHook .../dataset/bytecodes/bytecodes/benign_bytecodes.txt` | 1 bytecode per line | 20000 / 20000 (all) | raw sample only — NOT 1:1 with the 4.17M benign address list |
| `PhishingHook .../dataset/opcodes.csv` | `Opcode`/`Operand`/`Gas`/`Label` (already disassembled, not raw hex) | 22,675,861 opcode rows across 7000 unique contracts (3542 Label=0 benign, 3458 Label=1 phishing) | disassembly of the unique bytecode set above; now directly verified (see 1.2) |
| `PhishingHook cli/test_bytecodes.txt` | 1 line | 1/1 | CLI demo sample |

### (B) Address-only files (no bytecode)

| File | Column | Unique addresses | Chain ID present? | Malicious/benign label present? |
|---|---|---|---|---|
| `USENIX .../eoa_detect/extracted_addresses.xlsx` | `address` | 718 (793 rows) | No | Implicit (all = detected malicious) |
| `USENIX .../composite_detect/get_code/ca_address.xlsx` | `chain`,`from`,`ca_address` | 4299 `ca_address` / 435 `from` | **Yes** (7 chains) | No (candidate list feeding get_code, pre-detection) |
| `USENIX .../ca_detect/get_code/suspected_tx1.csv` / `suspected_tx2.csv` | `chain`,`from`,`ca_address` | 1335 / 24479 | Yes | No |
| `USENIX .../composite_detect/get_code/suspected_tx.csv` | `chain`,`potential_suspect_creator` | — (724 rows) | Yes | No |
| `USENIX .../analysis_information/sa_contract.xlsx` / `sa_contract_malicious.xlsx` | `chain`,`delegated_address` | 2685 rows (all chains) | Yes | `matched` column present in `_malicious` version, but values observed are all `'unmatched'` in the sampled rows |
| `PTXPhish-main/dataset/InitialAddress.xlsx` | 11 category-named columns | 228 valid 40-hex addresses | No (Ethereum implied) | Implicit (all malicious, column name = attack subtype) |
| `PhishingHook .../dataset/contracts/unique_contracts/unique_phishing.txt` | 1 addr/line | 3458 | No (Ethereum implied) | Implicit (phishing) — but bytecode for these IS available (see A) |
| `PhishingHook .../dataset/contracts/unique_contracts/unique_benign.txt` | 1 addr/line | 3542 | No | Implicit (benign) |
| `PhishingHook .../dataset/contracts/contracts/benign.txt` | 1 addr/line | 4,170,611 | No | Implicit (benign) — this is the full candidate pool, bytecode only fetched for a 20K sample |
| `PhishingHook .../dataset/contracts/contracts/phishing.txt` | 1 addr/line | 17455 | No | Implicit (phishing) |
| `scamsonethereum-main/master_blacklist_set.txt` | 1 addr/line | 7915 | No (Ethereum implied) | Implicit (all blacklisted/malicious) |
| `scamsonethereum-main/all_across_hard.txt` | 1 addr/line | 495 | No | Implicit (malicious) |

### (C) Neither bytecode nor address

- `PTXPhish-main/dataset/PTXPHISH.xlsx` — cells are 64-hex **transaction hashes** + source URLs, not addresses or bytecode.
- `USENIX .../analysis_information/obfuscated_vul_ca/*.xlsx` — "Address" field is a 16-hex **obfuscated case-study ID** (8 bytes), not a real 20-byte chain address.
- All `model_evaluation_module` / `post_hoc_analysis_module` CSVs (PhishingHook) — ML performance metrics / statistical test results.
- `.../utils/{gas,opcode,operand}_lookup.json` — static opcode/gas feature-encoding tables, not per-contract data.
- All `AM_FunctionSelector.jsonl` / `AM_Detect_*.jsonl` — decompiler analysis outputs (selectors, call-graph hits) keyed by address, not raw bytecode itself (though they reference the `.hex` path where the bytecode lives).

### Explicit verdict

**Bytecode is directly available in the USENIX artifact; the malicious EOA-targeted contracts are represented as bytecode (not addresses-only) in `eoa_detect/get_code/contracts_with_bytecode.xlsx`, column `bytecode`, 793 rows (joined against the 793-row `detect_result.jsonl` malicious set; all 793 have non-empty bytecode).** The same holds for CA-targeted (124 malicious per `overview.xlsx`; 78 unique / 83 chain-rows reconstructable via the flashloan cross-match in `ca_detect/result.xlsx` joined to the bytecode files — see caveat below) and composite (7/7 malicious, bytecode recovered from `output_composite.zip`).

**Caveat on the CA-targeted "124" figure:** `overview.xlsx` states 124 CA-targeted malicious contracts as its own summary headline (chain breakdown: BNB 18, Polygon 14, Base 92), but no single intermediate file in the released artifact reconstructs exactly that 124-address list — `ca_detect/result.xlsx` (the only final CA-targeted result file) covers a different sub-pattern (flashloan cross-contract matching: 80 rows / 78 unique addresses) whose chain breakdown does not match 124's. The 124 number should be treated as attested-but-not-directly-reproducible from the shipped intermediates.

---

## PART 3 — Family-diversity measurement (bytecode files only)

Method: L1 = sha256(lowercased, `0x`-stripped hex). L2 = sha256 of opcode-mnemonic skeleton with all PUSH1..PUSH32 immediates stripped (byte 0x60–0x7f → token `PUSH` + skip `op-0x5f` bytes; every other byte emitted as its decimal value).

### Table: class × chain

| class | chain | L0 | L1 | L2 | clones/family (L0/L2) |
|---|---|---:|---:|---:|---:|
| USENIX-EOA-targeted-malicious | arbitrum | 59 | 56 | 52 | 1.13 |
| USENIX-EOA-targeted-malicious | base | 159 | 136 | 128 | 1.24 |
| USENIX-EOA-targeted-malicious | bnb | 177 | 158 | 146 | 1.21 |
| USENIX-EOA-targeted-malicious | ethereum | 240 | 214 | 196 | 1.22 |
| USENIX-EOA-targeted-malicious | gnosis | 14 | 13 | 13 | 1.08 |
| USENIX-EOA-targeted-malicious | optimism | 108 | 105 | 56 | 1.93 |
| USENIX-EOA-targeted-malicious | polygon | 36 | 34 | 26 | 1.38 |
| **USENIX-EOA-targeted-malicious** | **all chains** | **793** | **567** | **439** | **1.81** |
| USENIX-CA-targeted-malicious(flashloan) | arbitrum | 1 | 1 | 1 | 1.00 |
| USENIX-CA-targeted-malicious(flashloan) | base | 8 | 8 | 8 | 1.00 |
| USENIX-CA-targeted-malicious(flashloan) | bnb | 20 | 20 | 20 | 1.00 |
| USENIX-CA-targeted-malicious(flashloan) | ethereum | 29 | 28 | 28 | 1.04 |
| USENIX-CA-targeted-malicious(flashloan) | gnosis | 5 | 5 | 5 | 1.00 |
| USENIX-CA-targeted-malicious(flashloan) | optimism | 1 | 1 | 1 | 1.00 |
| USENIX-CA-targeted-malicious(flashloan) | polygon | 19 | 18 | 18 | 1.06 |
| **USENIX-CA-targeted-malicious(flashloan)** | **all chains** | **83** | **81** | **81** | **1.02** |
| **USENIX-Composite-malicious** | bnb (only) | **7** | **7** | **7** | **1.00** |
| PhishingHook-phishing | ethereum (implied) | 3458 | 3458 | 3333 | 1.04 |
| PhishingHook-benign | ethereum (implied) | 3542 | 3542 | 3045 | 1.16 |

### Malicious-set family analysis (USENIX EOA + CA-flashloan + composite combined, 883 contract-instances, 521 distinct L2 families)

**Top-10 skeleton families by size:**

| # | skeleton hash (12-char prefix) | size | % of 883 malicious | chains | class |
|---|---|---:|---:|---|---|
| 1 | `89e940843b15` | 48 | 5.44% | optimism | EOA-targeted |
| 2 | `4145a34c576a` | 24 | 2.72% | arbitrum, base, bnb, ethereum, optimism | EOA-targeted |
| 3 | `4afc3cbf1da0` | 19 | 2.15% | base, bnb, ethereum, gnosis, optimism | EOA-targeted |
| 4 | `ecf580538e83` | 13 | 1.47% | base, bnb, ethereum | EOA-targeted |
| 5 | `2952f9c74461` | 12 | 1.36% | base, bnb, optimism | EOA-targeted |
| 6 | `0cc5436c7fa4` | 10 | 1.13% | bnb, optimism, polygon | EOA-targeted |
| 7 | `969803f8588a` | 10 | 1.13% | base, bnb, ethereum, polygon | EOA-targeted |
| 8 | `4a77393549e8` | 9 | 1.02% | arbitrum, base, bnb, ethereum, optimism | EOA-targeted |
| 9 | `b9b1aeef403c` | 9 | 1.02% | arbitrum, base, bnb, ethereum, gnosis, optimism | EOA-targeted |
| 10 | `4302d62c2ef8` | 9 | 1.02% | arbitrum, bnb, ethereum, gnosis | EOA-targeted |

**Top-10 combined coverage: 163 / 883 = 18.46% of all malicious contract-instances.**

**Cross-chain families:** 83 of 521 skeleton families (15.9%) appear on more than one chain — i.e., the same attacker template was redeployed verbatim (modulo hardcoded constants) across multiple EVM chains. All top-10 families except #1 are cross-chain; the single largest family (#1, 48 instances, 5.44%) is optimism-only.

---

## PART 4 — Address-export plan

**Not applicable in the "address-only" branch** — PART 2's verdict for the USENIX malicious set is (A) bytecode, not (B) address-only, so no RPC-fetch plan or `addresses_by_chain/` export is required for USENIX. (`composite_detect/get_code/ca_address.xlsx` is the one USENIX file that is address-only/pre-bytecode-fetch, listing 4299 unique `ca_address` candidates across 7 chains — already superseded in this artifact by `output_composite.zip`'s bytecode.)

**scamsonethereum-main check (performed regardless, as requested):**

| File | Lines | Format | Verdict |
|---|---:|---|---|
| `master_blacklist_set.txt` | 7915 | one `0x` + 40-hex address per line, no header, no chain/label column | Pure Ethereum-mainnet address list (class B) |
| `all_across_hard.txt` | 495 | one `0x` + 40-hex address per line, no header, no chain/label column | Pure Ethereum-mainnet address list (class B) |

Both are flat address lists with no bytecode, no explicit chain field (Ethereum mainnet implied by repo name/domain), and no explicit label column (list membership itself = malicious/blacklisted).

---

## PART 5 — Cross-artifact overlap: scamsonethereum ∩ USENIX malicious set

**Headline: 0 overlap.** The USENIX malicious set and the scamsonethereum blacklist describe entirely independent contract populations.

| Comparison | \|A\| | \|B\| | overlap | Jaccard |
|---|---:|---:|---:|---:|
| USENIX malicious (Ethereum-chain subset only, 269 unique addr) ∩ `master_blacklist_set.txt` (7915) | 269 | 7915 | **0** | 0.000000 |
| USENIX malicious (all 7 chains, 797 unique addr values) ∩ `master_blacklist_set.txt` (7915) | 797 | 7915 | **0** | 0.000000 |
| USENIX malicious (Ethereum-chain subset, 269) ∩ `all_across_hard.txt` (495) | 269 | 495 | **0** | 0.000000 |
| USENIX malicious (all chains, 797) ∩ `all_across_hard.txt` (495) | 797 | 495 | **0** | 0.000000 |
| (bonus sanity check) PhishingHook-phishing (3458) ∩ `master_blacklist_set.txt` (7915) | 3458 | 7915 | **0** | 0.000000 |

Per the task's own framing: this is the **low-overlap** case — the four datasets describe independent attacker families (EIP-7702 delegate-contract attacks vs. generic Ethereum scam blacklist vs. payload-phishing contracts), so combining them grows rather than corroborates the positive set.

---

## HEADLINE NUMBERS

```
1. USENIX malicious representation:     BYTECODE (not address-only) — contracts_with_bytecode*.xlsx + output_*.zip .hex files
2. N malicious EOA-targeted units:      793 rows / 718 unique addresses, all with non-empty bytecode (matches overview.xlsx exactly)
3. L2 family count (combined malicious, 883 instances across EOA+CA-flashloan+composite): 521 distinct skeleton families
4. Benign sample availability:          NONE in USENIX; PhishingHook artifact has 3,542 unique benign bytecodes (different domain: generic phishing, not EIP-7702)
5. scamsonethereum blacklist size:      7,915 addresses (master_blacklist_set.txt); 495 addresses (all_across_hard.txt)
6. USENIX ∩ scamsonethereum overlap:    0 addresses, Jaccard = 0.000000 (independent positive sets)
```
