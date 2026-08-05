# Pilot Code Evidence Report

Branch `tps-revision-v3`. This phase responds directly to the finding that
`Pilot_Simple_Review.xlsx` (the prior simplified workbook) contained only opcode-count
summaries — no source, no decompiled pseudocode, no readable evidence contributors could
actually use to check the AI's conclusions. That workbook is left unmodified as archived
infrastructure, alongside all Phase 3A files. **`Pilot_Code_Review.xlsx` is the new,
code-evidence-backed workbook and is the one to send to contributors.**

The 20 frozen Pilot items were not resampled. `gold_dev_manifest.csv` and
`gold_test_manifest.csv` were not modified (verified below).

## 1. Verified-source retrieval

Every one of the 20 Pilot addresses was checked live against two independent, keyless
source registries:

- **Sourcify v2** (`https://sourcify.dev/server/v2/contract/{chainId}/{address}`)
- **Blockscout v2** (`https://{chain}.blockscout.com/api/v2/smart-contracts/{address}`, one
  instance per chain: eth/optimism/base/arbitrum/polygon/bsc/gnosis.blockscout.com)

**Result: 0 of 20 Pilot items have verified source on either registry.** This is consistent
with the manifest's own `pilot_reason: known_disagreement` tag — these items were sampled
specifically because they are structurally ambiguous, not because they are well-known
verified contracts.

For the 2 confirmed DELEGATECALL proxy items (`polygon:0x32ab10eb...`,
`optimism:0x06831533...`), the real implementation address was resolved on-chain via
`eth_getStorageAt` (both resolve to the identical address `0xcfaa26ad40bfc7e3b1642e1888620fc402b95dab`
on their respective chains — the same contract deployed at the same address on two networks).
That implementation is **also unverified** on both registries, but was fully decompiled (see
below): its complete function-selector set is an exact match to the **Safe (Gnosis Safe)**
multisig wallet's core interface (`execTransaction`, `checkSignatures`/`checkNSignatures`,
`addOwnerWithThreshold`, `removeOwner`, `swapOwner`, `changeThreshold`, `enableModule`,
`execTransactionFromModule`, `approveHash`, `getOwners`, `getThreshold`, `nonce`,
`domainSeparator`, `getTransactionHash`, `setGuard`, `VERSION` — 31 selectors total). This was
not verified byte-for-byte against a known Safe release (noted as an open question in the
workbook), but it is a specific, strong, positive signal, not a guess from selector names
alone — it is the complete interface, not a partial match.

**Number with verified source: 0/20.**
**Number with a resolved implementation: 2/20** (both proxies resolve to the same
Safe-interface-matching singleton). Three further non-proxy items also had a
`storage-slot-0` address resolved on-chain (used as an owner or forwarding destination, not
a delegate implementation) — see the workbook's `implementation_resolved` column for each.

## 2. Decompilation (fallback for all 20 — none had verified source)

Every item was decompiled with `evmole` (labeled disassembly with byte offsets, resolved
function selectors, storage layout), with every function selector — both cleanly dispatched
ones and selector-shaped constants found in fallback comparisons — looked up against
`4byte.directory` for a human-readable signature, plus ASCII-string extraction and
address/hash-constant extraction directly from the raw bytecode (already present locally in
the frozen manifest, no network call needed for this step).

**Number successfully decompiled: 20/20**, plus the 2 shared implementations that had
non-zero code (`0xcfaa26ad...` — the Safe-pattern singleton, 22,528 bytes — and
`0xfc968f28...` — a 23-byte stub referenced by `ethereum:0x2d33b68f...`). Two other resolved
addresses (`0x6702f2df...`, `0x1c99baf6...`) turned out to have **zero deployed code** —
i.e. they are plain externally-owned accounts, not contracts — which is itself informative
evidence (reported in the relevant items' `access_control_explanation` /
`asset_transfer_or_approval_explanation` columns) and correctly required no decompilation.

No item required marking `INSUFFICIENT_CODE_EVIDENCE` outright, but 3 items' AI reasoning
explicitly states the decompiled evidence, while real, was not enough to responsibly reach a
confident conclusion within this review's scope (see §3).

## 3. Access-control evidence

Beyond decompiling, every dispatched sensitive function across all 20 items was checked by
hand for `CALLER` (`msg.sender`) and `ORIGIN` (`tx.origin`) usage, tracing each occurrence to
determine whether it feeds a comparison/`JUMPI` (a real guard) or something else (e.g. an
event-log parameter, which is not a guard).

**Number with meaningful, concretely-traced access-control evidence: 17/20.** The remaining
3 (`base:0x7aef1df0...` — a large, apparent bridge/relay contract; `optimism:0x6cd575da...`
— a large AccessControl/ERC-4337-style contract; `bnb:0x8656e046...` — atypical bytecode
structure that defeated standard selector-dispatch recovery) were honestly left `UNCERTAIN`
rather than guessed at, consistent with the review's own stated standard.

Notable concrete findings surfaced only by this deeper pass (not visible from opcode counts
alone):

- **2 items use `tx.origin` for authorization** (`base:0x531723f8...`, `base:0x399e3a4f...`)
  — the well-documented SWC-115 phishing-vulnerable pattern, one of them guarding a
  `SELFDESTRUCT` path.
- **3 items have a confirmed, exhaustive absence of any caller check anywhere in the
  contract** on a function that performs an arbitrary external call or asset transfer
  (`base:0xbe4cb4f3...`, `arbitrum:0xc9a6f7ff...`, `ethereum:0x1c8ef3d4...`) — in each case
  traced across the *entire* disassembly, not a truncated prefix.
- **1 item's CREATE (contract-deployment) capability was confirmed unrestricted**
  (`base:0x2e8bf58e...`).
- **5 items have a confirmed, concrete, appropriate access-control guard** (owner-only,
  self-call-only, owner-or-self, or a single fixed authorized address), upgrading them from
  Phase 3A's `UNCERTAIN` to `SAFE` with real evidence rather than an absence of red flags —
  most notably `base:0x09551d2a...`, where all 5 of its asset-moving functions were
  individually confirmed gated by the identical owner-address comparison.

## 4. Updated AI label distribution

| Label | Phase 3A (opcode counts only) | This phase (code-grounded) |
|---|---|---|
| SAFE | 3 | **9** |
| UNSAFE | 0 | **6** |
| UNCERTAIN | 17 | **5** |

The shift is a direct consequence of evidence depth, not a change in standard: the same
"UNCERTAIN when insufficient" rule was applied throughout, but most items that were
previously `UNCERTAIN` purely because a 60-opcode prefix and aggregate counts couldn't show
a guard now have that guard (or its absence) directly traced and cited by bytecode offset.

## 5. Exact locations of downloaded source and decompiled files

```
revision_v3/human_eval/pilot_code_evidence/
  <chain>_<address>/                        one folder per Pilot item (20 total)
    verification_status.json                Sourcify + Blockscout raw results
    README.md                                short human-readable summary
    decompiled/
      disassembly.txt                        full labeled disassembly, byte offsets
      functions.json                         dispatched + fallback-candidate selectors,
                                              4byte.directory-resolved signatures
      storage.json                           storage slot layout (evmole)
      constants.json                         notable PUSH20 address-shaped constants
      strings.txt                            ASCII strings extracted from raw bytecode
  _shared_implementations/<address>/          same structure, for the 2 resolved,
                                              non-zero-code implementation addresses
  _fetch_summary.json                        machine-readable run summary
  _selector_cache.json                       4byte.directory lookup cache (reused across items)
```

No verified source files exist anywhere in this tree, because none of the 20 items (or their
2 resolved implementations) had verified source on either registry checked.

## 6. New files created this phase

- `revision_v3/experiments/excel_review/fetch_code_evidence.py` — the retrieval/decompilation
  pipeline (executed; produced everything under `pilot_code_evidence/`)
- `revision_v3/human_eval/llm_reviews/pilot_code_review_content.json` — the 20 per-item
  narrative/snippet records, each grounded in a specific file under `pilot_code_evidence/`
- `revision_v3/experiments/excel_review/build_code_review_workbook.py` — builds the workbook
- `revision_v3/human_eval/Pilot_Code_Review.xlsx` — **the new file to send to contributors**

## 7. Workbook structure (verified)

Exactly 2 sheets: `REVIEW_GUIDE`, `REVIEW_ITEMS`. `REVIEW_ITEMS` has exactly the 26 columns
specified (evidence, AI, contributor, group, lead-author), 20 data rows matching the frozen
manifest's `item_id` set exactly, 2 dropdowns (`contributor_label`, `final_label`, each
restricted to `SAFE,UNSAFE,UNCERTAIN`), `final_label`/`final_reason` locked with sheet
protection enabled, all contributor/group/final cells blank (0 non-blank), no forbidden
field substrings anywhere, and no raw bytecode or long opcode sequences in the sheet (`relevant_code_snippet`
contains only short, offset-anchored readable pseudocode excerpts, verified programmatically).

## 8. Confirmation

- `pilot_manifest.csv`, `gold_dev_manifest.csv`, `gold_test_manifest.csv`,
  `gold_test_hashes.json` MD5 hashes are unchanged from the Phase 3A baseline — no
  resampling.
- No `Gold_Dev_Review.xlsx` / `Gold_Test_Review.xlsx` or equivalents exist.
- `Pilot_Simple_Review.xlsx`, `Pilot_Review.xlsx`, `Pilot_Master_Adjudication.xlsx`, and every
  other Phase 3A file are unmodified.
- `revision_v2/experiments/common/frozen.py verify` reports `OK: 144 frozen files verified
  unchanged`.
- No human labels were fabricated: `contributor_label`, `contributor_reason`,
  `group_discussion`, `final_label`, and `final_reason` are blank for all 20 rows.

## Stop condition compliance

Contributor review was not started. Gold-Dev and Gold-Test workbooks were not created. No
model was retrained or evaluated. No manuscript file was touched.
