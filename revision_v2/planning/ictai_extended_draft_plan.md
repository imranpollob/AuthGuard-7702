# ICTAI Reviewer Plan for the AuthGuard-7702 Extended Draft

**Purpose.** This plan defines the argument, evidence standard, and manuscript structure for a
standalone extended draft. It treats the completed revision artifacts as the source of truth and
does not modify the frozen paper or frozen experimental artifacts.

## 1. Reviewer assessment before rewriting

An ICTAI reviewer is likely to find the problem timely and practically motivated, but acceptance
will depend on whether the paper makes a narrow technical claim and supports it without leakage,
benchmark inflation, or operational overstatement. The rewrite must address the following risks.

1. **Novelty must be precise.** EIP-7702 security analysis already exists, and ML-based bytecode
   analysis is not new. The defensible novelty is their intersection at a specific decision point:
   an EIP-7702-specific, ML-based, bytecode-only screener used before authorization. The paper
   must say “to our knowledge” and must not claim to be the first EIP-7702 detector overall.
2. **The architecture claim must follow model selection.** The completed experiments select the
   hierarchical sequence-only model. Multi-view fusion, auxiliary tasks, and
   transformation-consistent training did not produce the final gain. They belong in ablations or
   negative results, not in the contribution list.
3. **Dependence controls are central, not procedural detail.** Contract families and exact
   duplicates can make random splits misleading. Family-disjoint folds, duplicate constraints,
   matched partitions, and family-clustered uncertainty must be visible in the main paper.
4. **Labels define delegate risk, not universal vulnerability.** The model predicts the benchmark's
   task-aligned malicious/benign-cleared labels. It does not prove exploitability, semantic safety,
   or coverage of every EIP-7702 abuse pattern.
5. **Low-FPR evidence must accompany AUPRC.** A wallet-facing screener is useful only if recall is
   reported at operational false-positive budgets. The paper will foreground Recall@1%, 5%, and
   10% validation-matched FPR and report achieved FPR, rather than relying on one unconstrained
   classification score.
6. **Benign controls expose a real tradeoff.** The sequence model has stronger detection but does
   not establish a lower `benign_general` false-alert rate. The result must be reported directly
   and discussed as a thresholding and deployment tradeoff.
7. **Transformation results are bounded stress tests.** F200 and M3+F200 are protocol-defined
   bytecode transformations, not a proof of universal semantic preservation or robustness to an
   adaptive attacker. Execution checks are bounded evidence only.
8. **Latency scope must remain local.** The measured latency includes preprocessing, inference,
   policy evaluation, evidence extraction, and JSON-ready result construction. It excludes RPC,
   process startup, wallet UI, and user interaction. The paper must not call it end-to-end wallet
   latency.
9. **Interpretability must remain observational.** Reported indicators are deterministic opcode
   and selector observations. They are not path-sensitive reachability claims, causal
   explanations, or auxiliary-head predictions.
10. **Negative findings strengthen credibility.** First-STOP, canonicalization, feature fusion,
    multi-task learning, and transformation-consistent training should be documented compactly as
    rejected alternatives. They should not be allowed to blur the final system identity.

## 2. Paper thesis and final contributions

**Thesis.** A compact hierarchical opcode-sequence model can support pre-authorization screening
of previously unseen EIP-7702 delegate families, improving clean and bounded-transformation
detection over the strongest evaluated histogram+n-gram baseline while remaining practical for
local integration.

The manuscript will make exactly three contributions:

1. **AuthGuard-7702 screening tool:** a bytecode-only CLI/Python screening path for raw runtime
   bytecode, delegate addresses, and authorization entries, returning a calibrated score,
   validation-derived warning tier, direct evidence, provenance, and structured JSON.
2. **Hierarchical full-bytecode sequence architecture:** a chunked convolutional encoder with
   learned contract-level attention that covers the complete benchmark bytecode and avoids
   first-STOP or fixed-prefix shortcuts.
3. **AuthGuardBench-7702 and operational evaluation:** a task-aligned benchmark and protocol with
   family/duplicate controls, benign controls, matched-FPR policies, bounded transformations,
   paired family-clustered uncertainty, and local runtime measurements.

## 3. Planned manuscript structure

1. **Abstract:** decision point, method, benchmark, strongest clean/robustness results, latency,
   and one explicit limitation.
2. **Introduction:** EIP-7702 authorization boundary, gap in current defenses, technical
   challenges, system thesis, headline evidence, and three contribution bullets.
3. **Background and Related Work:** EIP-7702 semantics; emerging EIP-7702 defenses; ML bytecode
   analysis; dependence and problem-space transformations. Comparisons will be conceptual unless
   models were retrained on the same benchmark.
4. **Problem Definition and Threat Model:** inputs, outputs, defender knowledge, adversary,
   excluded information, deployment boundary, and claim boundary.
5. **System Architecture:** end-to-end workflow, input modes, opcode processing, warning policy,
   direct evidence, and implementation interfaces.
6. **Hierarchical Opcode-Sequence Model:** full-bytecode chunking, local convolutions, chunk
   attention, risk head, loss, calibration, and model selection.
7. **AuthGuardBench-7702:** data composition and provenance, family/duplicate controls,
   transformations, benign controls, and artifact structure.
8. **Experimental Methodology:** baselines, ablations, family-disjoint folds, seed protocol,
   matched-FPR metrics, bootstrap inference, and runtime protocol.
9. **Evaluation:** clean detection; architectural ablations; bounded-transformation robustness;
   operating points and benign controls; latency and model footprint.
10. **Discussion:** why the sequence view won, implications for wallet/security-tool integration,
    false-alert tradeoffs, and lessons from rejected designs.
11. **Limitations and Responsible Use:** label scope, dataset shift, transformation validity,
    proxies/dynamic behavior, calibration drift, RPC trust, and advisory—not safety-proof—output.
12. **Conclusion:** restate only supported findings.
13. **Extended appendices:** complete operating-point tables, model/training details, negative
    results, tool schema/example, and reproducibility pointers.

## 4. Evidence and presentation plan

### Main figures

- **System workflow:** separates the implemented local scorer, optional RPC/integration context,
  and offline training/calibration path.
- **Hierarchical encoder:** shows opcode tokenization, 256-token chunks, dilated local encoding,
  within-chunk pooling, cross-chunk attention, calibration, and policy output.
- **Clean and transformed performance:** compares the selected model with the strongest baseline
  on AUPRC and Recall@5% FPR.
- **Architecture ablation:** makes the validation-led selection and failed fusion variants visible.

### Main tables

- benchmark composition and dependence statistics;
- clean three-seed performance plus primary-seed paired confidence intervals;
- architecture and training ablations;
- F200 and M3+F200 stress-test results;
- matched operating points and benign-control false-alert rates; and
- local runtime, model size, and explicit measurement scope.

### Claim discipline

- Use “outperforms the strongest evaluated baseline on AuthGuardBench-7702,” never universal
  model superiority.
- Use “bounded-transformation robustness” or “stress-test performance,” never semantic
  equivalence or adversarial robustness without qualification.
- Use “local screening latency,” never end-to-end wallet latency.
- Use “directly observed indicators,” never proof of reachability or malicious intent.
- Report both three-seed descriptive results and the primary-seed paired family bootstrap, clearly
  identifying the aggregation used by each.

## 5. Deliverables and completion checks

The standalone manuscript will be created under `revision_v2/paper_extended/` with:

- `main.tex` and a local `references.bib`;
- reusable table fragments in `tables/`;
- source-controlled figure definitions and a reproducible plotting script in `figures/` and
  `scripts/`;
- a build README; and
- a compiled PDF if the local TeX toolchain supports the required packages.

Before handoff, every numerical claim will be traced to the completed benchmark, fusion,
bootstrap, or runtime artifacts; the manuscript will be compiled; undefined references and
citations will be resolved; frozen files will remain unchanged; and rejected contribution claims
will be absent from the title, abstract, and contribution list.
