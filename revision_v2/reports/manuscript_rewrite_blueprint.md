# AuthGuard-7702 Manuscript Rewrite Blueprint

This document is a prose and structure blueprint. It does not modify the current LaTeX
manuscript. All performance numbers and claim boundaries come from
`revision_v2/reports/final_contribution_decision.md`.

## 1. Recommended paper identity

### Title

**AuthGuard-7702: Hierarchical Bytecode Sequence Screening for EIP-7702 Delegation**

Alternative, if the benchmark should be more visible:

**AuthGuard-7702: Pre-Authorization Delegate Screening and Dependence-Aware Evaluation for
EIP-7702**

### One-sentence thesis

AuthGuard-7702 shows that a compact hierarchical opcode-sequence model can screen previously
unseen EIP-7702 delegate families before authorization, substantially outperforming the strongest
evaluated histogram+n-gram baseline under clean and bounded bytecode-manipulation conditions
while remaining small and fast enough for local integration.

### Final contribution identity

1. an operational EIP-7702 pre-authorization screening tool;
2. a hierarchical full-bytecode opcode-sequence architecture; and
3. AuthGuardBench-7702 with dependence-aware, adversarial, benign-control, and runtime evaluation.

Do not describe adaptive search, transformation-consistent training, first-STOP, canonicalization,
or feature fusion as contributions.

## 2. Draft abstract

EIP-7702 allows an externally owned account to delegate execution to contract code, creating a
security-critical decision before the account signs an authorization. At that point, a malicious
delegate may have no transaction history, reputation, or verified source code, limiting the value
of behavior-dependent defenses. We present AuthGuard-7702, an integration-ready, bytecode-only
screening tool that analyzes delegate runtime code before authorization and returns a risk score,
policy-derived warning level, directly observed security indicators, and structured output. Its
core is a hierarchical opcode-sequence model that encodes local instruction patterns in 256-token
chunks and aggregates contract-wide evidence through learned attention. We evaluate AuthGuard on
AuthGuardBench-7702, a task-aligned corpus with 2,280 primary contracts from 819 bytecode families,
797 additional benign controls, exact-duplicate controls, and bounded bytecode transformations.
Across three training seeds, the sequence model achieves mean family-disjoint AUPRCs of 0.931 on
clean bytecode, 0.910 under 200% donor-isolated flooding, and 0.910 under combined selector/address
rewriting and flooding, compared with 0.828, 0.577, and 0.563 for the strongest histogram+n-gram
XGBoost baseline. On the primary paired analysis, clean AUPRC improves by 0.057 (95% CI 0.002 to
0.118), while Recall@5% FPR improves by 0.212. The 0.743 MB model completes local preprocessing,
inference, policy evaluation, and evidence generation in 4.334 ms on average (p95 14.073 ms) over
3,000 CPU calls. These results establish the feasibility of lightweight pre-authorization
delegate screening while exposing a remaining benign-control false-alert tradeoff and clear
boundaries on semantic and wallet-level claims.

Suggested keywords: EIP-7702; account delegation; smart-contract security; bytecode sequence
learning; pre-authorization screening; adversarial robustness.

## 3. Introduction

The introduction should use six compact movements.

### Paragraph 1 — new security boundary

- Explain that EIP-7702 lets an EOA authorize a delegate address and execute its code in the
  authority account's context.
- Emphasize the capability and the new trust decision, not a generic smart-contract-vulnerability
  problem.
- State the consequence: malicious or overly permissive code can act using the EOA's authority.
- Cite the EIP and current EIP-7702 security studies.

### Paragraph 2 — why existing defenses are late or mismatched

- Transaction graphs, reputation, victim reports, and realized behavior become useful after
  activity occurs.
- Decompilation and cross-contract static analysis are valuable but represent a different cost and
  information point.
- Before signing, runtime bytecode may be the only stable technical artifact available.
- Formulate the gap: no established EIP-7702-specific ML bytecode screener at the authorization
  boundary was found in the reviewed literature.
- Use the narrow phrase “to our knowledge”; do not claim the first EIP-7702 detector overall.

### Paragraph 3 — technical challenge

Explain why ordinary bytecode classification is insufficient:

- related deployments and compiler variants create family dependence;
- exact duplicates can inflate random splits;
- long contracts exceed ordinary fixed-prefix sequence encoders;
- metadata, addresses, selectors, and unreachable padding can alter surface representations; and
- a wallet-oriented warning must operate at low FPR with bounded latency.

### Paragraph 4 — system idea

Introduce AuthGuard-7702 as a complete local screening path:

1. parse an authorization or receive a target address/bytecode;
2. obtain and normalize delegate runtime bytecode;
3. tokenize the complete opcode stream;
4. encode 256-token chunks with a lightweight convolutional encoder;
5. aggregate chunk evidence with attention;
6. calibrate the score and apply a validation-derived warning policy; and
7. return structured results and direct opcode evidence.

Clarify that no first-STOP truncation, decompiler, transaction history, family identifier, chain
identifier, or label-construction feature enters the selected model.

### Paragraph 5 — evaluation approach and headline result

- Introduce AuthGuardBench-7702 and the primary count: 2,280 contracts, 819 primary families.
- Mention the 797 benign-general controls and exact-duplicate grouping.
- State that histogram+n-gram XGBoost is the strongest baseline.
- Give the three-seed headline: 0.931 clean AUPRC versus 0.828; approximately 0.910 versus
  0.56--0.58 under both stress conditions.
- State the paired clean delta and low-FPR recall gain.
- Mention 4.334 ms mean local latency and 0.743 MB size.

### Paragraph 6 — contribution bullets

Use these bullets, with no fourth contribution:

1. **Operational pre-authorization screening.** AuthGuard-7702 accepts bytecode, delegate
   addresses, or authorization entries and emits calibrated policy warnings, direct evidence, and
   structured output.
2. **Hierarchical opcode-sequence learning.** The model preserves contract-wide coverage through
   chunk encoding and attention and significantly improves clean and bounded-adversarial detection
   over the strongest evaluated bytecode baseline.
3. **Dependence-aware benchmark and evaluation.** AuthGuardBench-7702 combines label provenance,
   family/duplicate controls, matched-FPR policies, benign controls, bounded transformations,
   paired uncertainty, and local runtime measurements.

## 4. Background and related work

Most of the current section can be retained, but its comparison logic must change.

### 4.1 EIP-7702 execution and authorization risk

- Distinguish the 23-byte delegation designator from the referenced runtime program.
- Explain why screening the authority account's designator would expose only an address.
- Summarize EOA-targeted, contract-targeted, composite, and phishing risks only to motivate the
  task.
- Do not suggest AuthGuard detects every EIP-7702 attack category.

### 4.2 Existing EIP-7702 detection

- Describe transaction/decompiler/cross-contract approaches as complementary.
- Explicitly acknowledge that existing work already detects malicious EIP-7702 activity.
- Define AuthGuard's narrower novelty: pre-authorization, ML-based, bytecode-only screening.

### 4.3 ML bytecode security

- Compare with PhishingHook, ContractWard, DLVA, Eth2Vec, or the subset that fits the page budget.
- Explain label and decision-boundary differences.
- Never compare their published accuracy directly with AuthGuardBench results.
- If methods are mentioned as baselines, say representative model families were retrained on the
  same benchmark.

### 4.4 Dependence and adversarial representations

- Retain family-dependence and problem-space transformation citations.
- Connect them directly to the benchmark design.
- State that bounded transformations do not prove semantic equivalence.

## 5. Problem definition and threat model

### 5.1 Input and output

Let `b` be the runtime bytecode at the delegate address. Define the model as

`s = sigmoid(f_theta(T(b)) / temperature)`,

where `T` is deterministic opcode tokenization. The external policy maps `s` to high, warning,
caution, or low-observed-risk tiers using validation-negative thresholds corresponding to nominal
1%, 5%, and 10% FPR.

The output is advisory. A low score is not proof of safety, and the score is not a probability of
theft.

### 5.2 Defender knowledge

Available:

- delegate address or runtime bytecode;
- optional RPC endpoint;
- authorization fields needed to resolve the delegate.

Unavailable to the model:

- future or historical transactions;
- source code and decompiler facts;
- signer balances, approvals, and identity;
- chain/address/family/fold identifiers; and
- source capability fields used during label collection.

### 5.3 Adversary

The evaluated adversary may rewrite metadata and selected immediates, rewrite sensitive selectors,
and add donor-isolated post-STOP bytes. The model is not claimed robust to arbitrary recompilation,
dynamic obfuscation, new malicious semantics absent from the labels, proxy-state changes, or
arbitrary control-flow rewrites.

### 5.4 Deployment boundary

Separate local scoring from network and wallet integration. RPC correctness, proxy resolution,
cache policy, UI design, user response, and end-to-end authorization latency are out of scope.

## 6. AuthGuard-7702 system architecture

This section must be rewritten completely. The existing 773-feature XGBoost description is no
longer the proposed system.

### 6.1 End-to-end workflow

Describe three input modes:

- raw runtime bytecode;
- delegate address plus RPC endpoint; and
- one EIP-7702 authorization entry.

Then show: resolve/fetch -> validate/normalize -> opcode chunks -> hierarchical encoder ->
temperature-scaled risk score -> matched-FPR policy -> structured warning and direct evidence.

The architecture figure should distinguish:

- dashed integration context: wallet, RPC/network, UI;
- solid implemented path: parsing, scoring, policy, evidence, JSON; and
- offline path: benchmark, family folds, training, validation calibration, saved model.

### 6.2 Full-bytecode sequence representation

- Normalize hexadecimal runtime bytecode.
- Perform deterministic linear-sweep disassembly.
- Map recognized instructions to stable opcode IDs; collapse PUSH widths consistently with the
  established tokenizer.
- Split the stream into 256-token chunks.
- Retain up to 64 chunks. All benchmark contracts fit because the maximum is 16,081 tokens, below
  16,384.
- For larger deployment inputs, sample chunks evenly over the stream rather than taking a prefix.
- Explain why this avoids first-STOP and prefix-only shortcut representations.

### 6.3 Hierarchical encoder

Give the actual architecture:

- opcode embedding dimension 32;
- first 1-D convolution, kernel 5;
- second dilated 1-D convolution, kernel 3 and dilation 2;
- GELU activations;
- max pooling over tokens within each chunk;
- learned attention across chunks;
- 128-dimensional fusion/risk representation and binary risk head; and
- temperature scaling on held-out validation logits.

The term “fusion” here should not be used for feature modalities. The final model is a single
opcode-sequence view with hierarchical local/global aggregation.

### 6.4 Warning policy and explanations

- Define thresholds on validation negatives only.
- Explain high/warning/caution tiers.
- Provide direct evidence from deterministic bytecode observations: call-family instructions,
  SSTORE, DELEGATECALL/CALLCODE, token/approval selectors, CREATE/CREATE2/SELFDESTRUCT.
- Describe these as observable surfaces, not reachable behavior or malicious intent.
- Do not report the discarded auxiliary-head predictions as tool explanations.

### 6.5 Implementation

- Python and PyTorch versions.
- 742,561-byte model artifact.
- CLI/Python API and JSON schema.
- State that the manuscript evaluates the scorer, not a wallet extension.

## 7. AuthGuardBench-7702 and methodology

### 7.1 Corpus and provenance

Use one dataset table with:

- malicious: 727;
- benign-cleared: 1,553;
- benign-general: 797;
- benign-AA: 5 case observations;
- primary total: 2,280; and
- complete total: 3,082.

Explain weak-negative semantics and label provenance. Keep the designator-resolution and
conflicting-label quarantine story, but shorten it to what is needed for task validity.

### 7.2 Family and duplicate controls

- 819 primary families.
- 2,528 unique bytecodes in the complete benchmark.
- 233 exact-duplicate groups containing 787 rows.
- Exact duplicates share a primary label and fold.
- Family IDs stay within one outer fold.
- Families are similarity clusters, not attacker identities.

### 7.3 Train/validation/test protocol

For outer fold `f`:

- test: fold `f`;
- validation: fold `(f+1) mod 5`;
- fitting: remaining three folds.

Use identical partitions for the sequence model and strongest baseline. State seeds 7702, 7703,
and 7704. Model selection should be described as validation-based: the sequence model had mean
seed-7702 validation AUPRC 0.9482, higher than every fusion and single-view alternative.

### 7.4 Baselines and ablations

Separate conventional baselines from architecture ablations.

Conventional baselines:

- opcode histogram RF/XGBoost;
- TF-IDF logistic regression and SVM;
- hashed n-gram XGBoost;
- histogram+hashed-n-gram XGBoost, the strongest baseline; and
- previous 773-feature AuthGuard XGBoost where space permits.

Ablations:

- dense-only neural branch;
- n-gram-only neural branch;
- sequence-only;
- feature fusion without auxiliary tasks;
- fusion with multi-task objective;
- source-balanced fusion; and
- transformation-consistent fusion.

### 7.5 Conditions and metrics

Primary conditions:

- clean M0;
- donor-isolated F200;
- M3+F200; and
- benign-general false-alert control.

Primary metrics:

- AUPRC;
- Recall at validation-matched 1%, 5%, and 10% FPR; and
- achieved FPR.

Secondary:

- Brier score;
- model size; and
- mean/p50/p95/p99 runtime.

Explain the 10,000-replicate paired family-clustered bootstrap. Fold means and pooled paired
metrics must be labeled separately because AUPRC is nonlinear.

## 8. Evaluation

Replace the old RQs with five contribution-aligned questions.

### RQ1 — Does hierarchical sequence modeling generalize to unseen families?

Use the three-seed fold-mean table:

| Model | Clean AUPRC | Recall@5% | achieved FPR |
|---|---:|---:|---:|
| sequence | 0.9309 | 0.8282 | 0.0463 |
| hist+n-gram XGB | 0.8276 | 0.5822 | 0.0631 |

Then report primary-seed paired pooled results:

- AUPRC delta +0.0571, CI [+0.0023, +0.1179];
- Recall@5% delta +0.2118, CI [+0.0952, +0.3390]; and
- achieved-FPR delta -0.0245, CI [-0.0466, -0.0047].

Interpretation: the model improves both ranking and low-FPR recall under the benchmark protocol.

### RQ2 — Which architecture component matters?

Show validation selection and test ablations. Main finding:

- sequence-only is best;
- n-gram and dense-only branches are weaker;
- combining views does not improve generalization;
- multi-task and consistency objectives do not explain the result.

This negative ablation is important because it shows the contribution is contract-wide sequence
modeling, not complexity for its own sake.

### RQ3 — How does the model behave under bounded bytecode manipulation?

Three-seed means:

| Condition | Sequence AUPRC | Baseline AUPRC | Sequence Recall@5% | Baseline Recall@5% |
|---|---:|---:|---:|---:|
| F200 | 0.9104 | 0.5765 | 0.7235 | 0.1714 |
| M3+F200 | 0.9102 | 0.5633 | 0.7189 | 0.1788 |

Primary paired deltas:

- F200 AUPRC +0.3314, CI [+0.2561, +0.4089];
- F200 Recall@5% +0.5805, CI [+0.4678, +0.6794];
- M3+F200 AUPRC +0.3254, CI [+0.2561, +0.4016]; and
- M3+F200 Recall@5% +0.5461, CI [+0.4365, +0.6435].

Do not say “semantics-preserving robustness.” Say “robustness under the bounded transformation
protocol.”

### RQ4 — What false-alert tradeoff remains?

Report benign-general FPR at the matched 5% policy:

- sequence three-seed mean: 0.0616;
- baseline three-seed mean: 0.0452;
- primary pooled: 0.0853 versus 0.0376;
- paired delta CI crosses zero.

Interpretation: the sequence model's detection gains do not justify claiming uniformly lower
false alerts. Policy selection and richer benign validation remain deployment requirements.

### RQ5 — Is local screening operationally lightweight?

Report 3,000 CPU calls:

- mean 4.334 ms;
- p50 3.172 ms;
- p95 14.073 ms;
- p99 16.906 ms;
- model load 10.047 ms; and
- model size 0.743 MB.

The timing includes sequence preprocessing, inference, warning policy, direct evidence, and
JSON-ready result construction. Exclude RPC, startup, wallet UI, and network paths.

## 9. Discussion

### 9.1 Why sequence-only wins

Offer hypotheses, clearly labeled as interpretation:

- local opcode ordering contains behavior patterns lost in histograms;
- chunk attention can focus on informative regions and discount appended donor bytes;
- dense and hashed views may reintroduce global distribution sensitivity under flooding; and
- the small corpus may not support the extra parameters and objectives in feature fusion.

Do not claim attention provides causal explanation unless separately validated.

### 9.2 What the robustness result means

- It shows stability under the implemented transformation family.
- The sequence model was clean-trained, so its robustness is architectural rather than caused by
  transformation-consistent training.
- It does not imply robustness to arbitrary compiler changes, instruction substitution,
  control-flow flattening, proxy-state changes, or new malicious behaviors.

### 9.3 Operational value

- The tool can be a first-stage warning before authorization.
- It can complement transaction intelligence and heavyweight static analysis.
- High-risk output could trigger a block or deeper analysis; intermediate output could trigger a
  warning; low output still carries residual risk.
- The study does not evaluate user behavior or whether warnings prevent losses.

### 9.4 False-alert and calibration limitations

- Discuss the benign-general 6.16% mean FPR.
- Note variation across seeds, especially seed 7702.
- State that a production wallet needs target-environment calibration and threshold governance.
- Labels are artifact-aligned and weak negatives are not verified benign ground truth.

### 9.5 Validity limitations

Include:

- label coverage and weak negatives;
- family construction is approximate;
- same benchmark used for architecture evaluation, although model selection was validation-based;
- no temporal or truly future deployment cohort in the final claim;
- bounded transformation validity;
- no wallet/RPC/UI end-to-end latency;
- fold model used for runtime measurement;
- no user study; and
- priority claim is literature-review bounded and must use “to our knowledge.”

## 10. Conclusion draft

EIP-7702 moves contract-code trust into the authorization path of established EOAs, motivating
security analysis before transaction history or reputation is available. AuthGuard-7702 provides
an integration-ready, bytecode-only screening tool for this decision point. Its hierarchical
opcode-sequence model learns local instruction patterns across complete contracts and, under
family-disjoint AuthGuardBench-7702 evaluation, improves clean and bounded-adversarial detection
over the strongest evaluated histogram+n-gram baseline. The selected 0.743 MB model completes
local scoring and evidence generation in 4.334 ms on average, demonstrating practical feasibility
as a first-stage warning component. The results are bounded by artifact-aligned labels, a
benign-control false-alert tradeoff, and transformation and deployment limitations. AuthGuard is
therefore best understood as a fast pre-authorization risk signal that complements, rather than
replaces, transaction intelligence, semantic analysis, and wallet policy.

## 11. Tables and figures

Recommended main-paper elements:

1. **Figure 1:** authorization-boundary workflow and implemented/deployment boundary.
2. **Figure 2:** hierarchical chunk encoder and attention pooling.
3. **Table 1:** benchmark composition, family counts, and controls.
4. **Table 2:** clean baseline and architecture-ablation comparison.
5. **Table 3:** F200 and M3+F200 AUPRC/Recall@5% comparison.
6. **Table 4 or compact text:** benign-general FPR and runtime/model size.

Move to appendix if page-limited:

- all 1% and 10% operating points;
- per-fold and per-seed values;
- full adaptive-search query statistics;
- first-STOP audit details;
- complete transformation-consistent training table; and
- extended CLI schema example.

## 12. What to retain, replace, and delete

### Retain with editing

- EIP-7702 background and designator/runtime distinction;
- transaction/decompiler versus pre-authorization information boundary;
- task-alignment and label-conflict quarantine;
- family and duplicate dependence argument;
- weak-negative and deployment limitations; and
- relevant bibliography entries.

### Replace completely

- title and abstract;
- final paragraphs and contribution bullets in the introduction;
- system architecture figure;
- 773-feature/XGBoost proposed-model description;
- evaluation RQs and headline tables;
- runtime section;
- discussion of what causes the model gain; and
- conclusion.

### Delete or demote

- “production-ready” and unqualified “real-time” language;
- feature fusion or transformation-consistency as the proposed contribution;
- adversarial augmentation as a contribution;
- first-STOP or canonicalization as a method;
- claims of lower benign-general FPR;
- semantic-equivalence language; and
- end-to-end wallet latency implications.

