# Phase 0 — AuthGuard-7702 Recon & Label Extraction Report

Scope: read-only reconnaissance of the four extracted artifacts. No model training. All figures below are derived from files physically present on disk in this session (no network fetches performed for this phase).

---

## TASK 1 — Capability facts in the USENIX decompile outputs

**HEADLINE: The `eoa_detect` pipeline ships only two narrow, verdict-defining fact files — not a general capability database. One encodes "external call reachable from `receive()`/`fallback()`" (this literally *is* the malicious-detection rule, 793/793 malicious contracts), the other is a pure function-name string match. Richer facts (full function inventory, delegatecall/create2 flags, call-graph edges) are computed by the pipeline's own Datalog rules but were not shipped for this pipeline.**

### Inventory

`USENIX EIP-7702 artifact/eoa_detect/decompile/` contains only 2 data files (plus `analyze.dl`, `main.py`, `run_analysis.sh`, `env.yaml`, `utils/`):

**`AM_Detect_SensitiveSigName.jsonl`** — 68 lines (69 unique `(chain,address)` keys, 64 unique addresses)
Schema (JSON keys): `address` (string, 0x+40hex), `path` (string, `output/<chain>/<addr>.hex`), `result` (array of `[selectorHex, functionSignatureText]` pairs).
Sample rows:
```
{"address": "0x2f1211e38436327cc90408565ea2f16dfc082600", "path": "output/optimism/0x2f1211e38436327cc90408565ea2f16dfc082600.hex", "result": [["0xb4", "sweep(address[])"]]}
{"address": "0xbe7ae1e53867f9f1778c8b728b533c00900a38be", "path": "output/optimism/0xbe7ae1e53867f9f1778c8b728b533c00900a38be.hex", "result": [["0x1c0", "sweepTokens(address,uint256)"]]}
```
This is a pure lexical match: `analyze.dl` (lines ~100-115) hardcodes prefixes `attack/hack/sweep/steal/drain/exploit/pwn` (and capitalized variants) and flags any public function whose decompiled name starts with one of them. It says nothing about reachability, call targets, or dataflow — it is a naming heuristic, not a capability fact.

**`detect_result.jsonl`** (identical copy also at `eoa_detect/detect_result.jsonl`) — 792 lines, 793 unique `(chain,address)` keys, 866 individual result rows across those keys (most contracts have exactly 1 row; 34 have 2; a handful have 3-9).
Schema: `address`, `path`, `result` (array of 4-element tuples: `[callStmtId, enclosingFuncSig, calleeStmtId, calleeSigText]`).
Sample rows:
```
{"address": "0x638b4f9ff3ccefc9a55abcc413af362b1a319d92", "path": "output/optimism/0x638b4f9ff3ccefc9a55abcc413af362b1a319d92.hex", "result": [["0x193b", "receive()", "0x90", "UnkownCall"]]}
{"address": "0xbec420215162d2e6a5bd6cb23a2bd86620a9d0fc", "path": "output/optimism/0xbec420215162d2e6a5bd6cb23a2bd86620a9d0fc.hex", "result": [["0x1e", "fallback()", "0x83", "UnkownCall"]]}
```
Field 2 (`enclosingFuncSig`) is **always** `"receive()"` (765/866 rows) or `"fallback()"` (101/866 rows) — never a named function. Field 4 (`calleeSigText`) is `"UnkownCall"` in 822/866 rows (95%, meaning the call target's function signature could not be statically resolved), and in the remaining 44 rows resolves to a real signature: `transfer(address,uint256)` ×17, `withdraw(uint256)` ×6, `approve(address,uint256)` ×5, `deposit()` ×4, `release(bytes32,uint256)` ×2, `safeTransferFrom(address,address,uint256)` ×1, plus a few one-offs. This file is, by construction, the Gigahorse/Datalog rule `AM_Detect_FallbackCallOut_High` (name inferred from `env.yaml`'s `GIGA.RULES` list; the rule's exact Datalog definition lives in an unshipped `clientlib/vulnerability_macros.dl` include, so this mapping is inferred from field values + naming convention, not directly verified against source): *"this contract's `receive()`/`fallback()` contains an external call statement."* Since every one of the 793 confirmed-malicious contracts has ≥1 row here, **this file is the malicious-label-defining signal itself**, not an independent capability layer on top of the label.

### What the `analyze.dl` rule file *declares* vs. what was *shipped*

`eoa_detect/decompile/analyze.dl` (115 lines) declares richer intermediate predicates — `AM_FunctionSelector`, `AM_FuncInfo`, `AM_Visualize_ExternalCallInfo` (func, callStmt, callOp, calleeVar, numArg, numRet, sigText, callFuncSig), `AM_Analysis_ExternalCallInfo` — and `eoa_detect/decompile/env.yaml`'s `GIGA.RULES` list configures 6 rules to run: `AM_FuncInfo`, `AM_Detect_FallbackCallOut`, `AM_Detect_FallbackCallOut_High`, `AM_Detect_DelegateCall`, `AM_Detect_Create2`, `AM_Detect_SensitiveSigName`. Per `main.py`'s logic, a `.jsonl` is only written per rule if that rule produced hits, and intermediate per-contract Gigahorse output directories are `sudo rm -rf`'d immediately after each contract. **Only 2 of those 6 configured rules' outputs were kept in the shipped artifact** (`SensitiveSigName` and the file renamed `detect_result.jsonl`, most likely `FallbackCallOut_High`) — `AM_FuncInfo`, `AM_Detect_FallbackCallOut` (plain), `AM_Detect_DelegateCall`, and `AM_Detect_Create2` were computed by the pipeline but not redistributed. By contrast, the sibling `ca_detect/` and `composite_detect/` pipelines *do* ship `AM_FunctionSelector.jsonl` (3,681 lines, full selector→address map) and `AM_Detect_FlashloanCall.jsonl` (69 lines, 5-field rows including a resolved `callFuncSig` hex) — but these cover a **different contract population** (CA-targeted / composite attacks, not the EOA-delegate set) and don't help fill the 7702-delegate gap.

### Explicit verdict

**Neither shipped `eoa_detect` file is a general per-contract semantic capability database.** `detect_result.jsonl` conflates "capability fact" and "final verdict" — it only exists for contracts already judged malicious, and it encodes exactly one fact (external-call-from-fallback-or-receive, plus in ~5% of cases a resolved callee signature). `AM_Detect_SensitiveSigName.jsonl` encodes only function-name string matches. There is no call-graph edge list, no ERC-20/NFT-transfer detector, no explicit "attacker-controlled destination" boolean, and no per-contract data for the 1,657 cleared/benign contracts at all (see Task 2). A "learned capability surrogate" trained only on these fields would really be learning to reproduce the existing name/reachability heuristics on the malicious side, with zero benign-side supervision.

---

## TASK 2 — Label coverage across classes

**HEADLINE: Capability facts are positives-only. 793/793 (100%) of confirmed-malicious contracts have a `detect_result.jsonl` row (tautologically, since that file *is* the malicious criterion); only 11/1,892 (0.6%) of cleared contracts have *any* fact at all (an unrelated `SensitiveSigName` string hit), and 0/1,892 have a `detect_result.jsonl`-style call-reachability fact.**

Join performed on `(chain, lowercased delegated_address)`, deriving `chain` from each jsonl row's `path` field via regex, matching against `eoa_detect/get_code/contracts_with_bytecode.xlsx` (2,685 total candidates):

| | malicious (793) | cleared (1,892 = 2,685 − 793) |
|---|---:|---:|
| has `detect_result.jsonl` row | 793 (100%) | 0 (0%) |
| has `AM_Detect_SensitiveSigName.jsonl` row | 58 (7.3%) | 11 (0.6%) |
| has **any** capability-style fact | 793 (100%) | 11 (0.6%) |

(As a sanity check: all 793 `detect_result.jsonl` keys are found inside the 2,685-candidate pool — 0 orphans — confirming the malicious label and the candidate pool are consistently keyed.)

### Explicit verdict

**Positives-only.** There is no symmetric fact-extraction pass over the benign/cleared class — the pipeline runs Gigahorse's detection rules and only persists hits, so "no row" for a cleared contract means "rule did not fire" or possibly "never computed / discarded," not "verified absence of the capability." Any capability column derived from these files must be left `NULL` (unknown), not `False`, for the cleared and benign_general classes — labeling them `False` would fabricate negative evidence that was never collected.

---

## TASK 3 — Victim / signer context availability

**HEADLINE: Victim/signer EOA addresses are absent by design, confirmed both by the artifact's own ethics statement and by direct inspection of every file that could plausibly carry a "from" address. Relational/exposure scoring cannot use real signer addresses in this phase — only synthetic profiles.**

The top-level README (`USENIX EIP-7702 artifact/README.md`) states explicitly under **Ethics Statement**:
> "**No victim identification** – This dataset does not and cannot reveal the identities of victim addresses, ensuring that no sensitive or private user data is exposed."

I verified this holds in practice, not just in the README's claim:
- `grep -rliE "victim|signer|from_address|\"from\"|tx_hash|authorization_list|block_number|timestamp"` across every `.jsonl/.json/.py/.dl/.md/.csv` in the artifact returns only the README itself, plus 3 Python scripts (`composite_detect/decompile/crosscontract_sh/cross_match.py`, `cross_match_victim.py`, `composite_detect/get_code/get_contract_address.py`) — these reference "victim" only in the sense of victim *contracts* (CA-targeted pipeline, cross-contract call matching), not victim EOAs, and none of them touch the eoa_detect pipeline or its data files.
- The one file that could plausibly carry authorization-transaction metadata, `eoa_detect/get_code/suspected_txs.xlsx` (2,685 rows), has only 3 columns: `chain`, `delegated_address`, `count` — no signer/`from` address, no tx hash, no block number, no timestamp. `count` appears to be "how many times this delegate address was observed across scanned authorizations" (a popularity count for the delegate contract, not an identifier for who delegated to it).
- `analysis_information/sa_contract.xlsx` and `sa_contract_malicious.xlsx` (both 2,685-row, same `chain/delegated_address/count[/matched]` shape) are the same data re-surfaced for the paper's cross-referencing analysis — `matched` splits 826 "matched" vs. 1,859 "unmatched" against some external malicious-address list (unspecified in the artifact; not investigated further as it's out of scope for Task 3).

### Explicit verdict

**Victim data is absent, not merely unlinked.** No file anywhere in the USENIX artifact contains a signer/authorizer EOA address, an authorization-transaction hash, a block number, or a timestamp. Relational risk scoring relative to a signer's on-chain exposure must use **synthetic signer profiles** in this phase (or a later phase that explicitly re-derives signer addresses from public authorization-list data on-chain, which is feasible in principle since EIP-7702 authorizations are public on L1/L2 explorers, but that would require a fresh network-sourced dataset, not this artifact).

---

## TASK 4 — Verified-source coverage

**HEADLINE: 0 Solidity source files are shipped anywhere in the USENIX artifact. All 793 malicious contracts would need external fetching (e.g., Etherscan/chain-explorer "verified source" API) for any source-level mutation experiment.**

`find "USENIX EIP-7702 artifact" -iname "*.sol"` returns 0 results, across all three pipelines (`eoa_detect`, `ca_detect`, `composite_detect`) and `analysis_information/`. The artifact ships bytecode (`contracts_with_bytecode.xlsx`) and decompiled/Datalog facts, but never raw or verified Solidity. This phase does not fetch from Etherscan (per the read-only constraint); the actual verified-source hit-rate among the 793 is unknown until that live check is run in a later, explicitly network-authorized phase.

### Explicit verdict

**Local verified-source coverage: 0/793 (0%).** Plan for 793 external verification-status lookups if a source-level mutation experiment is pursued; expect a non-trivial fraction to be unverified (typical for freshly-deployed malicious contracts), so budget for a bytecode-only fallback path too.

---

## TASK 5 — Decompiler runtime

**HEADLINE: No runtime/timing figure exists anywhere in the artifact (README, scripts, configs) or in any paper file (no PDF is shipped). A live measurement was not attempted because Gigahorse requires a nontrivial local install (the `gigahorse-toolchain` submodule is not present, and the Soufflé Datalog compiler is not installed on this machine) — installing it was out of scope per your instruction not to do heavy setup.**

Checks performed:
- `grep -rniE "second|seconds| ms |millisecond|runtime|per contract|throughput|took [0-9]"` across all `.md/.py/.sh/.yaml/.txt` in the USENIX artifact: the only hit is an unrelated API-retry backoff message (`"Retrying in {delay} seconds..."` in `composite_detect/get_code/get_contract_address.py`) — not a decompiler timing claim.
- `find ... -iname "*.pdf"`: 0 results anywhere under `<WORKSPACE>` — the USENIX paper itself is not part of this artifact bundle, so no paper-quoted timing figure is retrievable locally.
- `find ... -iregex ".*gigahorse.*"`: 0 results — the `gigahorse-toolchain` the scripts assume (`./gigahorse.py`, `./gigahorse/clients/analyze.dl` per `run_analysis.sh` and the README's reproduction guide) is not vendored in this artifact; it's an external dependency (`github.com/nevillegrech/gigahorse-toolchain`).
- `which souffle`: not found. Soufflé (the C++ Datalog engine Gigahorse compiles its `.dl` rules to) is not installed, and installing it requires a full C++ toolchain build (cmake, a C++17 compiler, several hours on first build) — this is exactly the "nontrivial installation" case your instructions said to skip.

### What a real measurement would require
1. `git clone https://github.com/nevillegrech/gigahorse-toolchain` (not shipped).
2. Build/install Soufflé (`souffle-lang.github.io`) — nontrivial, platform-specific, often 20-60 min compile.
3. Install Gigahorse's Python requirements and copy `eoa_detect/decompile/{main.py,env.yaml,run_analysis.sh,analyze.dl}` into the cloned toolchain per the README's reproduction guide (`mv ... ./gigahorse` / `./gigahorse/clients`).
4. Run `sudo python3 ./gigahorse.py -C analyze.dl <hex>` per contract (the script requires `sudo`, i.e. root, for its cleanup/tempdir handling) and time it externally.

### Explicit verdict

**No defensible "decompiler takes ~X s/contract" number can be produced from this artifact alone.** Any speed claim used to justify a fast surrogate model must either (a) come from the published USENIX paper text directly (fetch the paper in a network-authorized phase and quote it with page/section), or (b) be measured firsthand after a real Gigahorse+Soufflé install, which is a multi-hour one-time setup cost, not something to do inline in a recon pass.

---

## TASK 6 — Capability dataset extraction

**HEADLINE: Reachable — but only for the malicious class. Produced `capability_dataset.csv`, 3,258 rows: 793 malicious (cap_* populated from `detect_result.jsonl`), 8 benign_AA + 800 benign_general + 1,657 benign_cleared (cap_* left NULL — no facts shipped, per Task 2's positives-only finding). `cap_transfer_native` could not be populated for anyone — no shipped fact captures msg.value / native-ETH movement.**

### Mapping (source field → capability column), documented per-row from `detect_result.jsonl`'s `result` tuples `[callStmtId, enclosingFuncSig, calleeStmtId, calleeSigText]`:

| Column | Populated for | Rule | Coverage (of 793 malicious) |
|---|---|---|---:|
| `cap_value_receiving_hook` | malicious only | `True` if any row's `enclosingFuncSig` ∈ {`receive()`, `fallback()`} | 793/793 (100% — tautological, this defines the malicious set) |
| `cap_transfer_native` | **nobody** | **Not derivable.** No shipped fact records `msg.value`/native-ETH transfer; `calleeSigText` only names the *called function*, never whether ETH was attached. Left NULL for all rows. | 0/793 (unmapped, flagged) |
| `cap_move_erc20` | malicious only | `True` if any row's `calleeSigText == "transfer(address,uint256)"` (unambiguous ERC-20 selector text; `transferFrom(address,address,uint256)` never observed in this file so not needed as a second match) | 11/793 |
| `cap_move_nft` | malicious only | `True` if any row's `calleeSigText` ∈ {`safeTransferFrom(address,address,uint256)`, `safeTransferFrom(address,address,uint256,bytes)`, `safeTransferFrom(address,address,uint256,uint256,bytes)`} (arities unique to ERC-721/1155; plain `transferFrom(address,address,uint256)` was deliberately excluded from this bucket since that selector is textually identical for ERC-20 and ERC-721 and never appeared here anyway) | 1/793 |
| `cap_grant_approval` | malicious only | `True` if any row's `calleeSigText == "approve(address,uint256)"` | 5/793 |
| `cap_unrestricted_external_call` | malicious only | `True` for every row present (existence of a `detect_result.jsonl` entry means Gigahorse's high-confidence fallback/receive-external-call rule fired at all) | 793/793 (100% — also tautological) |
| `cap_attacker_controlled_sink` | malicious only | `True` if any row's `calleeSigText == "UnkownCall"` (callee's target function could not be statically resolved — the standard proxy for "destination/selector is dynamic," not a direct "attacker-controlled" proof) | 779/793 (98.2%) |

**Two of the seven columns (`cap_value_receiving_hook`, `cap_unrestricted_external_call`) are tautologically true for 100% of the malicious rows** because they restate the detection rule itself rather than measuring an independent capability — flag this before using them as model features, since they carry zero discriminative information within the malicious class (though they remain informative *between* malicious and unlabeled/null classes, trivially).

`AM_Detect_SensitiveSigName.jsonl` (function-name matches) was **not** folded into any of the 7 capability columns — it measures naming convention, not a call-graph/dataflow capability, and mixing it in would blur the provenance documented above.

### `family_id_d3`

Reused the D1/D2/D3 clustering logic from `bracket_family_count.py` (opcode-4-gram MinHash + LSH-bucketed union-find, threshold 0.85), run **separately** for the malicious set and the combined negative set (namespaced IDs `M<root>` / `N<root>` to keep the two clusterings' arbitrary root-index numbering from colliding):

- Malicious (793 bytecodes): **275 D3 families** this run.
- Negative (2,465 bytecodes: 8 benign_AA + 800 benign_general + 1,657 benign_cleared): **1,306 D3 families** (matches the figure from the prior session's `cluster_negative_set.py` run exactly).

**Caveat — clustering is not perfectly reproducible run-to-run.** `bracket_family_count.py`'s `ngram_minhash()` hashes opcode 4-grams with Python's built-in `hash()`, and this process has `PYTHONHASHSEED` unset (confirmed: two bare `python3 -c "print(hash('abcd'))"` calls in this session returned different values). That randomizes which grams collide into the same MinHash slot across runs, which is why this run's malicious-family count (275) differs from the 250 you cited from an earlier session's run (~10% swing); the negative-set count (1,306) happened to reproduce exactly, but that's not guaranteed on a third run. **For a reproducible `family_id_d3` before any modeling, set `PYTHONHASHSEED=0` (or patch `ngram_minhash` to use a seeded hash like `hashlib.blake2b`) and re-run once, then freeze that assignment.** I did not do that here since you didn't ask for a reproducibility fix, but it's a blocker for anything downstream that depends on stable family IDs (e.g., group-aware train/test splitting).

### `capability_dataset.csv`

Written to `<WORKSPACE>/capability_dataset.csv`, 3,258 data rows, columns: `address, chain, family_id_d3, class, bytecode, cap_value_receiving_hook, cap_transfer_native, cap_move_erc20, cap_move_nft, cap_grant_approval, cap_unrestricted_external_call, cap_attacker_controlled_sink`.

`class` breakdown: `malicious`=793, `benign_cleared`=1657, `benign_general`=800, `benign_AA`=8. **Note:** your Task 6 spec listed only 3 class values (`malicious|benign_cleared|benign_general`); I added a 4th, `benign_AA`, for the 8 verified account-abstraction delegates built in the prior session, rather than silently dropping them or folding them into `benign_general` (where they'd misleadingly look like a random web sample instead of hand-verified legitimate implementations). Say the word if you'd rather I merge or drop that group.

Cap columns are empty-string (`""`, i.e. Pandas/CSV-null) for every `benign_*` row — this is intentional per Task 2's positives-only finding, not a bug.

---

## SCOPE DECISION

**(B) Reduced paper: capability surrogate (malicious side only) + mutation robustness experiments; relational/signer-exposure scoring restricted to synthetic case studies.**

Evidence:
- Task 1/2 rule out **(A) full paper**: capability labels exist for the malicious class only (100% coverage) and are essentially absent for the benign class (0.6%, and that 0.6% is an unrelated naming heuristic, not the same fact type). A model can't learn "capability → malicious vs. benign" from *labeled* capability facts on both sides — at best it can learn a malicious-side capability *surrogate* (e.g., "predict whether Gigahorse's fallback-call rule would fire, from bytecode/opcode features alone, without running Gigahorse") and validate that surrogate's capability predictions only where ground truth exists (the 793).
- Task 3 rules out any **victim-exposure-based relational scoring** grounded in real accounts: no signer/victim address survives anywhere in the artifact, confirmed by both the ethics statement and direct file inspection. Relational risk scoring can only proceed via synthetic/hypothetical signer profiles (e.g., "given a signer with N ETH and M ERC-20 approvals, what's the expected loss under this delegate's capability profile") as illustrative case studies, not real victim-grounded evaluation.
- Task 4 confirms a source-level mutation experiment is feasible in principle (793 addresses to look up) but needs a live Etherscan-style verified-source fetch pass first — not blocking, just sequenced after this phase.
- Task 5 means the "fast surrogate beats slow decompiler" framing has no artifact-local runtime number to cite yet; that number must come from either the published paper (fetch it) or a real Gigahorse+Soufflé install (multi-hour one-time cost) before it can be used as a headline claim.
- Task 6 shows the surrogate is buildable today: 793 labeled malicious rows across 275 opcode-similarity families (i.e., real family diversity, not a handful of clones) with 5 of 7 target capability columns populated at meaningful (non-degenerate, non-tautological) rates (`cap_move_erc20` 1.4%, `cap_grant_approval` 0.6%, `cap_move_nft` 0.1%, `cap_attacker_controlled_sink` 98.2%) — enough signal for a within-malicious-class capability classifier, not enough (with zero benign supervision) for a benign-vs-malicious capability classifier.

This is not **(C) blocked** — there is real, non-fabricated capability signal to build on, just narrower and more asymmetric than a "full paper" would need.
