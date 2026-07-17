# AuthGuard-7702 Three-Contribution Implementation Plan

## Objective

Build one coherent research system whose claims are separated by role:

1. **AuthGuard-7702** is the pre-authorization screening artifact.
2. **AuthGuard-Fusion** is the EIP-7702-specific multi-view, multi-task model.
3. **AuthGuardBench-7702** is the dependence-aware benchmark and operational evaluation.

Earlier first-STOP, adaptive-search, and augmentation experiments are supporting evidence only.
They are not promoted to standalone contributions. Frozen inputs and results remain read-only.

## Claim contract

### C1: screening tool

The finished tool accepts raw runtime bytecode, a delegate address plus RPC endpoint, or an
EIP-7702 authorization object. It returns a model score, a validation-derived warning level,
observable risk indicators, model provenance, and structured JSON. "Integration-ready" means a
stable CLI/Python/JSON interface; it does not imply a shipped wallet extension.

### C2: risk-modeling architecture

AuthGuard-Fusion has three independent views:

- a learned hierarchical opcode-sequence encoder;
- a hashed opcode 4-gram encoder; and
- a dense opcode-histogram and structural-security encoder.

The main head predicts malicious-delegation risk. Auxiliary heads predict explicitly defined,
bytecode-observable security factors. A source-balanced consistency loss may be applied to
bounded transformations. A robustness improvement is claimed only where paired uncertainty
excludes zero; otherwise the paper says the objective was evaluated.

### C3: benchmark and evaluation

AuthGuardBench-7702 packages label provenance, immutable sample identifiers, frozen family
splits, duplicate controls, benign controls, bounded transformations, matched-FPR evaluation,
per-row predictions, uncertainty, and local runtime measurements. Runtime stages are reported
separately: scorer core, process/model loading, RPC fetch, and complete CLI invocation.

## Primary decision rule

The primary operational metric is family-disjoint recall at a validation-matched 5% FPR.
AUPRC is the primary threshold-free metric. Recall at 1% and 10% FPR, benign-general FPR,
alerts per 1,000, calibration, robustness, model size, memory, and latency are secondary.

No superiority claim is made unless the paired family-clustered 95% interval supports it.
The strongest current baseline is histogram+hashed-4-gram XGBoost and must be included.

## Implementation order

1. Build the benchmark manifest and observable auxiliary targets.
2. Build and test AuthGuard-Fusion.
3. Add source-balanced transformation-consistency training.
4. Build the CLI/Python scorer and output schema.
5. Run identical-fold baselines, ablations, calibration, robustness, and runtime measurements.
6. Write `revision_v2/reports/final_contribution_decision.md` before touching the manuscript.

## Auxiliary targets

The original `cap_*` fields are partial positive provenance and are not complete supervised
targets. The model instead learns six reproducible observable factors for every bytecode:

1. external-call surface (`CALL`, `CALLCODE`, `DELEGATECALL`, or `STATICCALL`);
2. persistent-state write surface (`SSTORE`);
3. delegate/proxy surface (`DELEGATECALL` or `CALLCODE`);
4. token-movement selector surface (`transfer`, `transferFrom`, or `safeTransferFrom`);
5. approval selector surface (`approve`); and
6. code-lifecycle surface (`CREATE`, `CREATE2`, or `SELFDESTRUCT`).

These are observable risk indicators, not claims that an operation is malicious or reachable.
They regularize the learned representation and support faithful evidence reporting.

## Model success outcomes

- **Performance win:** statistically supported low-FPR or AUPRC improvement over the strongest
  baseline without material benign-FPR or clean-performance regression.
- **Operational win:** comparable detection with validated factor outputs and acceptable local
  runtime/model size. Frame as an interpretable operational architecture, not a superior model.
- **No win:** retain the strongest simple model in the tool and keep AuthGuardBench-7702 as the
  methodological contribution. Report the architecture result without promotion.

