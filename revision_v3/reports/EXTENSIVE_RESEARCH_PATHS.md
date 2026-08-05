# Reviewer-Driven Research Paths for AuthGuard-7702

Status date: 2026-08-04
Purpose: development roadmap and claim boundary, not manuscript-ready results.

Freeze update: the final post-cutoff protocol is now preregistered before human labels. The
primary 150-family post-cutoff set remains untouched, a disjoint 150-family replication reserve is
locked, the strongest histogram+n-gram XGBoost baseline is included in the final retraining, and
the project-balanced weight-8 DCRG is kept as a separately named training-intervention variant.
The primary statistical unit is a conservative signer/deployer/project dependence cluster (124
clusters for 150 primary items), not an exact runtime. Human results and project attribution are
still pending, so none of this converts development outcomes into manuscript claims.

## Current reviewer verdict

The project has a timely and defensible problem: **screen the runtime bytecode proposed in an
EIP-7702 authorization before the user signs, when transaction history and reputation may not
yet exist**. The current sequence model and family-disjoint benchmark establish feasibility, but
they do not yet establish a sufficiently distinctive technical method. A paper whose headline is
only "hierarchical bytecode classification" is vulnerable because bytecode learning, CFG
representations, graph neural networks, expert-feature fusion, and selective classification all
have substantial prior art.

The [EIP-7702 specification](https://eips.ethereum.org/EIPS/eip-7702#security-considerations)
itself says delegated code has unrestricted account access and must be closely audited. Therefore
AuthGuard must be framed as a **warning and triage aid**, never as evidence that a wallet can
safely expose arbitrary delegation or as a replacement for audit/allowlisting.

The strongest plausible paper is instead a bounded security-analysis paper with three linked
ideas: an EIP-7702-specific decision point, an authority-relative capability/guard representation,
and leakage-safe evaluation under realistic label and deployment shift. Each must be earned by an
experiment below; none should be claimed merely because it is implemented.

## Closest-work matrix and novelty boundary

| Prior work | What it already establishes | What AuthGuard must not claim | Remaining defensible distinction |
|---|---|---|---|
| [Huang et al., USENIX Security 2026](https://www.usenix.org/conference/usenixsecurity26/presentation/huang-mingyuan) | Large-scale EIP-7702 threat measurement; transaction filtering, decompilation, cross-contract analysis, and specialized rules; 924 malicious contracts across seven chains | First EIP-7702 detector, first static detector, or first real-world malicious-contract study | Pre-authorization, bytecode-only screening of a proposed delegate without requiring historical transactions |
| [Qi et al., EIP-7702 Phishing Attack](https://arxiv.org/abs/2512.12174) | Three activation pathways, ERC-4337 interaction, cross-chain authorization risk, and ecosystem measurement | First phishing analysis or first account-takeover characterization | A concrete, evaluated decision aid at authorization time |
| [Shao et al., USENIX Security 2026](https://www.usenix.org/system/files/conference/usenixsecurity26/sec26_prepub_shao.pdf) | Large-scale EOA/address misuse measurement including EIP-7702 delegations | First empirical evidence of malicious EIP-7702 use | Prospective assessment of previously unseen delegate code rather than retrospective incident mining |
| [DLVA, USENIX Security 2023](https://www.usenix.org/conference/usenixsecurity23/presentation/abdelaziz) | Learned EVM-bytecode vulnerability detection and low-latency inference | First learned bytecode analyzer or operational bytecode ML | EIP-7702 task alignment, authority semantics, and authorization-time operating contract |
| [Liu et al., IJCAI 2021](https://doi.org/10.24963/ijcai.2021/379) | Contract graphs plus expert security patterns and neural message passing | First graph/expert fusion for smart-contract security | A typed graph whose nodes and edges encode EIP-7702 authority, guard, capability, and explicit analysis gaps |
| [COBRA](https://arxiv.org/abs/2410.20712) and [EGFL](https://doi.org/10.1016/j.jss.2024.112118) | Bytecode CFG learning, function/interface context, local/global graph features | First CFG-based bytecode learner or first long-range graph model | Delegation-context semantics and comparison against capability-only and untyped controls on the same frozen families |
| [Pasqua et al., JSS 2023](https://doi.org/10.1016/j.jss.2023.111748) | Precise EVM CFG recovery using symbolic stack execution | First EVM CFG recovery; any claim that bounded recovery is sound or complete | First-class uncertainty/coverage evidence carried from analysis into the authorization decision |
| [Geifman and El-Yaniv, NeurIPS 2017](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html), [SelectiveNet, ICML 2019](https://proceedings.mlr.press/v97/geifman19a.html), and [El-Yaniv and Wiener, JMLR 2010](https://jmlr.csail.mit.edu/papers/v11/el-yaniv10a.html) | Selective classification, risk-coverage analysis, and abstention are established ideas | Novelty from adding DEFER or thresholding a score | A security-specific coverage gate, evaluated under family and temporal/project shift |
| [Hallberg Szabadvary et al., 2025](https://arxiv.org/abs/2506.21802) and [Bai and Jin, 2026](https://arxiv.org/abs/2603.24704) | Finite-sample/conformal approaches to error-controlled selective prediction | Distribution-free guarantees without exchangeability evidence | An empirical risk-control study that explicitly shows where guarantees fail under label/distribution shift |
| [Solidity metadata documentation](https://docs.soliditylang.org/en/latest/metadata.html) | Compiler appends a CBOR metadata map and two-byte encoded length to bytecode | Novelty from stripping standard compiler metadata | A correctness fix: exclude only exactly validated metadata from the conservative opcode census, and quantify its effect |

## Paths, tests, and decision rules

### Path A — Risk-controlled LOW / WARN / DEFER policy: **NO-GO as a main contribution**

Implemented a development-only policy that selects a LOW threshold on COMPLETE validation items
using a one-sided Clopper--Pearson risk bound, a WARN threshold at nominal 5% validation FPR, and
DEFER otherwise. It behaves as intended on inherited labels but fails on the current human-label
proxy:

| Target LOW risk | Inherited test LOW coverage / risk | Proxy Gold-Test LOW coverage / risk |
|---:|---:|---:|
| 5% | 5.48% / 1.67% | 10.19% / 36.36% |
| 10% | 15.51% / 1.85% | 24.07% / 42.31% |

Interpretation: the failure is semantic/distribution shift, not a thresholding bug. The paper may
retain WARN/DEFER and a risk-coverage curve, but it must not advertise LOW as certified safe. With
the coverage-v2 features, the proxy endpoint becomes worse: 61.0% of items assigned
LOW_OBSERVED_RISK are proxy-UNSAFE. The final interface should therefore use a neutral phrase such
as `NO_MODEL_WARNING` rather than `LOW`, and incomplete analysis should remain `DEFER`. A
newer selective-prediction method cannot repair a mismatched reference distribution by itself.

Artifacts: `results/selective_policy_path/risk_controlled_dcrg_policy.json` and
`experiments/selective_policy/run_risk_controlled_dcrg_policy.py`.

### Path B — Coverage-correct Delegation-Context Risk Graph: **TECHNICALLY SUCCESSFUL; no inherited-label performance gain**

Problem found: the original soundness census scans the entire runtime and therefore interprets
bytes in the Solidity CBOR metadata trailer as opcodes. In the 1,665 unique primary runtimes,
1,565 (93.99%) have an exactly decodable, known-shape metadata map. Those trailers contribute
1,745 false sensitive/context instruction sites, including 83 `CALL`, 65 `DELEGATECALL`, and 85
`SELFDESTRUCT` bytes. This can falsely force PARTIAL coverage.

Implemented change: identify the metadata boundary only when the length-delimited object decodes
exactly as a non-empty CBOR map with documented Solidity keys and value shapes. Malformed,
unknown, multi-object, and ambiguous suffixes remain executable. This is not semantic
canonicalization and does not use first-`STOP` pruning.

The second correction applies conservative state widening after eight visits to a program
counter: varying non-control constants become unknown, so conditional exits are explored in both
directions; valid `JUMPDEST` constants remain concrete, and any unresolved transfer still forces
PARTIAL. Comparison provenance remains part of state equivalence.

Label-free full-population result from the **format-valid metadata** intermediate:

| Extractor | COMPLETE unique runtimes | PARTIAL unique runtimes | COMPLETE primary samples |
|---|---:|---:|---:|
| Original bounded CFG | 517 / 1,665 (31.1%) | 1,148 | 670 / 2,190 (30.6%) |
| Exact metadata correction only | 662 / 1,665 (39.8%) | 1,003 | 871 / 2,190 (39.8%) |
| Metadata + state widening | 1,084 / 1,665 (65.1%) | 581 | 1,453 / 2,190 (66.3%) |

Relative to the original extractor, 567 unique runtimes move PARTIAL→COMPLETE and none move
COMPLETE→PARTIAL. Incomplete-function findings fall from 645 to 59 unique runtimes; the remaining
gaps are preserved. State widening is used in 1,843 analyzed functions, while 49 unresolved-jump,
seven stack-underflow, and 66 residual cap flags remain visible rather than being relabeled safe.
The extractor report's hashes were checked against the executed sources.

Adversarial review found that exact CBOR validation is still insufficient: metadata bytes remain
part of EVM code and a malicious runtime can jump to an instruction-aligned `JUMPDEST` inside a
valid trailer. The retained candidate therefore also requires the metadata start to be an
instruction boundary, the preceding instruction to terminate, and the trailer disassembly to
contain no `JUMPDEST`. Under this final rule, 1,455/1,665 runtimes exclude a trailer; 115
format-valid trailers are conservatively retained (59 contain `JUMPDEST`, 38 overlap an
instruction, and 18 permit fallthrough). Final COMPLETE coverage is 1,063/1,665 unique runtimes
(63.8%) and 1,416/2,190 primary samples (64.7%). Relative to the original extractor, 546 runtimes
move PARTIAL→COMPLETE and none regress. Source hashes and Python/cbor2/evmole versions match the
completed report.

Acceptance criteria:

1. **Passed:** unit tests demonstrate that malformed and unknown suffixes, PUSH-overlapping CBOR,
   and jump-target-bearing metadata are retained; real pre-metadata capabilities remain counted.
2. **Passed:** COMPLETE coverage increases materially without suppressing analyzer-limit warnings.
3. **No predictive claim:** the format-valid intermediate changed inherited-label AUPRC by only
   +0.00041 with a confidence interval crossing zero. The final fenced version changes mean
   inherited-label AUPRC from 0.95409 to 0.95375 (delta -0.00034, 95% CI
   [-0.00617, 0.00423]). Coverage correctness is therefore the contribution; performance is not.
4. **Passed:** the extractor reports the new metadata/widening rule, source hashes, and a versioned
   output boundary.

If the coverage change is large but predictive metrics do not improve, it remains a valuable
validity correction, not a model-performance contribution.

Under the development-only current-label proxy, final full DCRG reaches 0.93885 AUPRC. It beats
the untyped-guard ablation by +0.00427 (95% CI [+0.00076, +0.01023]) and the sequence model by
+0.04615 ([+0.00449, +0.09178]). The capability-only interval and histogram+n-gram baseline
interval cross zero, and protocol-actor removal is neutral. This supports continuing with a
guard-aware DCRG hypothesis, not claiming that every typed relation or actor feature contributes.
Because this proxy has driven method selection, a new untouched human set is mandatory.

### Path C — Relational graph encoder and local motifs: **NO-GO**

The current DCRG is reduced to fixed aggregate features and XGBoost. A reviewer can reasonably
say that this does not learn the graph structure. We compared:

1. current typed aggregate DCRG;
2. type-erased/untyped graph control;
3. capability-only graph control;
4. relational message passing over node and edge types;
5. sequence + relational graph fusion.

The relational run was stopped for mathematical futility after nine complete fold-seed runs:
typed relational AUPRC averaged 0.610 and untyped relational AUPRC 0.636. Even AUPRC=1.0 on all
six remaining typed runs could raise the final mean only to about 0.766, far below aggregate DCRG
AUPRC 0.952. The parameter-identical untyped control kept every relation matrix active through a
shared mean, so this is not explained by a smaller parameter budget.

The data-efficient alternative encoded entrypoint-local typed guard/capability motifs. Adding
them to aggregate DCRG produced AUPRC 0.95395 versus 0.95242 for aggregate DCRG, but the paired
family-bootstrap delta is -0.00052 under pooled OOF scoring (95% CI [-0.00653, 0.00658]); it also
does not beat type-erased motifs. Typed motifs alone reach only 0.635 AUPRC.

The original go criterion was family-clustered AUPRC improvement whose confidence interval
excludes zero against
the strongest aggregate DCRG, plus stable Recall@5% FPR and no materially worse legitimate-control
false-alert rate. It fails. The paper must not call the DCRG a learned graph architecture; it
should present it as an auditable typed security representation and use the simpler aggregate
model.

### Path D — Real authority-context evaluation: **REPRESENTATION ESTABLISHED; labels pending**

The historical primary rows contain delegate implementation addresses but not the authorizing
EOA. Consequently, authority-relative comparisons are UNKNOWN there. The post-cutoff snapshot
already recovers 708 real `(authority EOA, delegate runtime)` pairs (673 unique runtimes) from
authorization-tuple signatures. With the final jump-fenced coverage-correct extractor, 462/708
pairs are COMPLETE, up from 222/708; 246 remain PARTIAL.

Actual authority makes fixed-address guard relations decidable for 317/708 pairs (44.8%): 22 have
only authority matches, 290 only mismatches, and five contain both. This establishes that the
representation is exercised on real data, but not that it improves correct decisions. Among the
20 runtimes observed with more than one authority, the aggregate match/mismatch counts do not
vary, so the current snapshot does not support a stronger within-bytecode causal claim.

Required safeguards:

* **Done:** collect by a fixed cutoff and record transaction/block provenance;
* group all related project/bytecode families before splitting;
* hold out every family already used as a legitimate registry source and retrain;
* never score registry projects with a model trained on the same family;
* report malicious, legitimate, ambiguous, and failed-resolution coverage separately once the
  independent review is complete.

Go criterion: authority-relative edges must alter a meaningful number of decisions and improve
human-reviewed error analysis beyond bytecode-only capability counts. Otherwise authority context
is a design motivation/limitation, not an empirical contribution.

### Path E — Temporal and legitimate-project generalization: **DEVELOPMENT SUCCESS; untouched projects and labels pending**

This is the key reviewer defense against family leakage and stale attack families. Complete the
post-cutoff collection and project-family audit, retrain with mandatory family holds, and compare
sequence, aggregate DCRG, relational DCRG (if retained), and fusion on the untouched snapshot.

Go criterion: report uncertainty intervals and project-level outcomes; do not require every
metric to improve. A credible result may be that the method finds known malicious structure but
defers on novel or legitimate account implementations. Never replace missing human decisions
with inherited source-rule labels.

Development result with the final extractor: unit-weight project augmentation still warns on
14/30 documented legitimate deployments under leave-one-project-out evaluation. Project-balanced
benign weight totals of 8, 32, and 64 were explored with the prior coverage-correct candidate and
all reduced that to 1/30. The retained weight-8 rule also yields 1/30 with the final extractor
while preserving mean primary AUPRC 0.95135 and Recall@5% FPR 0.98108, compared with 0.95204 and
0.98526 under unit weighting. Weight 8 is the smallest tested successful value. This is promising
but not final evidence: the same eight projects exposed the weakness and selected the weighting
rule, and the paired eight-project warning-rate bootstrap is -0.4333 with 95% CI
[-0.8571, 0.0000]. Newly collected legitimate projects must be the final test.

### Path F — Measurement/benchmark fallback: **AVAILABLE**

If Paths C--E do not yield a defensible method improvement, the strongest honest paper is a
benchmark and validity study:

* demonstrate how duplicate/family leakage, compiler suffixes, label semantics, and operating
  thresholds inflate apparent security performance;
* release family-controlled bytecode, human adjudication protocol, DCRG evidence, and temporal
  controls;
* show which proposed defenses fail (first-`STOP`, uncertified LOW, direct registry scoring,
  weak-negative interpretation) and why.

This can be novel and useful, but only after human adjudication is completed and the paper is
framed around empirical findings rather than a state-of-the-art detector claim.

## Target three-contribution package

These are **conditional target contributions**, not current claims:

1. **Problem and benchmark.** The first leakage-controlled benchmark and human-adjudicated study
   of bytecode-only, pre-authorization EIP-7702 delegate screening, with exact-duplicate,
   project-family, and temporal controls plus an explicit ambiguous class.
2. **Authority- and coverage-aware method.** A Delegation-Context Risk Graph that connects
   reachable capabilities to typed authorization evidence and actual authority context while
   exposing unresolved control flow; retain “learned relational graph” only if Path C beats the
   aggregate representation.
3. **Deployment evidence, not a safety guarantee.** A staged WARN/DEFER decision aid evaluated at
   fixed false-alert budgets on human-reviewed, legitimate-project, and post-cutoff data, with
   negative results showing why nominal LOW-risk certification does not transfer across label
   semantics.

## Reviewer stop conditions

Do not submit the method paper until all of these are true:

* Gold-Test has independent human labels and recorded adjudication; the current proxy can guide
  development but cannot be called human labeling.
* The untouched final evidence boundary remains unused for further model selection after labels
  are revealed.
* At least one method comparison has paired, family-clustered uncertainty excluding zero, or the
  paper explicitly adopts the measurement/benchmark framing.
* Legitimate controls use project-family holdout and retraining rather than address-only filtering.
* Claims distinguish pre-authorization bytecode screening from retrospective transaction-based
  detection.
* LOW means “low observed model score” unless a valid calibration population and finite-sample
  risk statement are both established; it never means safe.
* Every incomplete analyzer result maps to DEFER and remains visible in artifacts.
