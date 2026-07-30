# Legitimate EIP-7702 Candidate Report — Phase 2, Part 9

Built by `revision_v3/experiments/external_controls/build_legitimate_candidates.py` from
`benign_7702_bytecode.csv` (repo root — itself produced by the existing
`fetch_benign_7702_delegates.py`'s `SEED_DELEGATES` list, each entry carrying a cited
documentation URL). Cross-referenced, read-only, against
`revision_v2/data/authguardbench_7702_v2.csv.gz` to attach family/population metadata where
the address survived task alignment. Outputs:
`revision_v3/external_controls/legitimate_candidates_all_deployments.csv` (45 rows, one per
chain-deployment), `legitimate_candidates_unique_bytecode.csv` (30 rows, one per distinct
project-bytecode pair), `legitimate_candidates_summary.json`.

## Headline numbers

| Quantity | Value |
|---|---:|
| Documented projects | **8** |
| Total chain-deployments (rows) | 45 |
| Unique project-bytecode pairs | 30 |
| Distinct runtime bytecode hashes overall | 30 |
| Present in the v2 primary benchmark (any chain) | 21 of 45 |

## Why this is below the brief's 20–50 target — and why it is not padded

The audit brief's own instruction governs this directly: **"Target: 20-50 distinct legitimate
implementations/families **if evidence supports that many**."** It does not. The repository's
only source of *documented* legitimate EIP-7702 delegates is the 8-project `SEED_DELEGATES`
list (Biconomy Nexus, Uniswap Calibur, Alchemy SemiModularAccount7702, ZeroDev Kernel v3.3,
OKX SmartWalletEntry, MetaMask StatelessDeleGator, Ambire EIP7702Account, Coinbase
EIP7702Proxy) — each with one citable source URL (a project's own docs or GitHub deployment
registry). No second, independent source of documented legitimate delegates was found in the
repository (the `legitimate_registry_expansion_v1` overlap audit mentioned in the Phase 1
codebase audit lives only on an unmerged branch and was, by its own text, "Phase 0 discovery
only... cannot establish a population benign FPR" — six *manually transcribed* addresses from
a public registry page, not independently verified deployments; it was not pulled into this
pass, consistent with not fabricating or padding the candidate list from a source this
project's own prior audit already flagged as insufficient).

**The right response to a target not met by available evidence is to report the true number,
not to lower the bar for what counts as "documented."** Per the audit brief's explicit
constraint (repeated from Phase 1's `LABEL_CLAIM_CONTRACT.md` and honored again here): a
source-rule-unflagged primary delegate is *never* auto-classified as legitimate just to pad
this list toward 20–50. Expanding this set legitimately would require new work — e.g.
systematically scanning verified-source registries (Sourcify, per-chain explorer
verified-contract APIs) for AA/7702-delegate-pattern contracts and manually confirming project
identity — which is future work, not something to fabricate here.

## Per-project detail (see JSON for full machine-readable version)

| Project | Chains deployed | Byte-identical across all deployed chains? | In v2 primary benchmark? |
|---|---:|:---:|:---:|
| Biconomy Nexus v1.3.1 | 7 | **No** — differs by one embedded 32-byte constant per chain | Yes |
| Uniswap Calibur v1.1.0 | 5 | Yes | Yes |
| Alchemy SemiModularAccount7702 | 6 | Yes | Yes |
| ZeroDev Kernel v3.3 (7702) | 6 | **No** | Yes |
| OKX SmartWalletEntry | 6 | **No** | Yes |
| MetaMask StatelessDeleGator | 7 | Yes | Partially (dropped in task alignment as a designator row on some chains) |
| Ambire EIP7702Account | 2 | Yes | Partially |
| Coinbase EIP7702Proxy | 1 | Yes (n=1, single chain) | Partially |

This reproduces and confirms, with a fresh independent computation, the cross-chain
non-identity finding already flagged in `PROJECT_AUDIT_FOR_TPS.md` §9.1: 3 of 8 projects
(Biconomy, ZeroDev, OKX) are **not** byte-identical across every chain they deploy to, so a
single frozen "family" representative per project (as the canonical v2 benchmark currently
stores, per `family_assignment_frozen.csv`) does not capture their per-chain bytecode
variation. `legitimate_candidates_unique_bytecode.csv` records all 30 distinct
(project, bytecode) pairs individually for exactly this reason.

## Deduplication method

Deduplication is **per-project**, not global: `project_bytecode_key = project_name +
":" + runtime_bytecode_sha256`. A global dedup (ignoring project identity) would risk silently
merging two different projects' code if they ever happened to share a byte-identical
implementation (not observed here, but not something to assume can't happen for common
proxy/forwarder patterns) — per-project dedup is a stricter, more defensible standard.

## Fields recorded per candidate

Project, chain, address, `runtime_bytecode_sha256`, code size, `family_id`/`family_size`
(from v2, where present), documentation URL. **Not available offline** (explicitly marked, not
fabricated): third-party audit report links (`SEED_DELEGATES` cites only project
documentation, never a separate audit firm's report) and on-chain confirmation that the
address was ever actually used in a live EIP-7702 authorization (requires the temporal
collector or an archive-node query — see `TEMPORAL_COLLECTION_REPORT.md`; not attempted here).
Deployment dates are likewise not recorded in the source data and are marked
`NOT_AVAILABLE_OFFLINE` rather than guessed.

## For later human verification

This candidate list is explicitly a **pre-verification inventory**, not a finalized
legitimate-control set — per the audit brief, "Create a candidate list for later human
verification." None of these 30 unique bytecodes have been added to any Gold-Dev/Gold-Test
sample or evaluation in this phase; they remain available as a future qualitative/external
control pool, same role as Phase 1's 5-item `QUALITATIVE_CONTROL` population.
