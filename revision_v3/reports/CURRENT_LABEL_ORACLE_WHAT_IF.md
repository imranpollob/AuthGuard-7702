# Current-Label Oracle What-If

Date: 2026-08-04  
Status: **planning diagnostic only; not human evidence and not submission results**

> **Superseded model snapshot:** this report records the original-extractor counterfactual. The
> retained jump-fenced extractor and final path decision are reported in
> `RESEARCH_ENDPOINT_AND_SUBMISSION_PLAN.md`. The central conclusion is unchanged: guard-aware
> DCRG is promising, while LOW/safety and protocol-actor superiority are unsupported.

## Assumption tested

This run treats the existing Opus-5 provisional Gold-Test labels as if they were final human
judgments: `UNSAFE` is positive, `SAFE` is bounded-negative, and `UNCERTAIN` is excluded as an
indeterminate outcome. The models, thresholds, feature groups, and 150-item sample remain those
in the pre-label SHA-256 scoring lock.

The assumption does not make the labels scientifically independent. The provisional reviewer
saw source-analyzer and CFG guard-dominance evidence, is not a human reviewer, and produced 42
uncertain outcomes. These numbers answer “what would the endpoint look like?” only.

## Proxy population

- 88 `UNSAFE`, 20 `SAFE`, and 42 `UNCERTAIN` items.
- 108 binary items; 28.0% excluded as uncertain.
- Binary proxy/source-rule agreement is 57.4%, showing that the proxy is not merely a copy of
  the source label, but not proving independence because analyzer evidence was visible.
- Unsafe prevalence among binary items is 81.5%; a raw AUPRC must therefore be interpreted
  against a prevalence baseline of 0.815 rather than against zero.

## Main frozen-model endpoint

| Model | Mean AUPRC | Mean AUROC | Recall | Observed FPR |
|---|---:|---:|---:|---:|
| Sequence | 0.893 | 0.654 | 0.424 | 0.117 |
| Full DCRG | **0.937** | **0.734** | **0.492** | **0.050** |
| Fixed noisy-OR fusion | 0.925 | 0.714 | 0.473 | 0.117 |

Paired family-clustered results:

- Fusion minus sequence AUPRC: +0.0322, 95% CI [+0.0082, +0.0556].
- Fusion minus DCRG AUPRC: -0.0125, 95% CI [-0.0387, +0.0083].

Thus context improves the sequence view, but fusion is not better than DCRG. The defensible
method endpoint is DCRG alone, not fusion.

## Representation novelty endpoint

| Full DCRG comparison | AUPRC difference | Paired 95% CI | Proxy conclusion |
|---|---:|---:|---|
| Capability-only CFG | +0.0173 | [+0.0020, +0.0400] | Supported |
| Untyped guards | +0.0105 | [+0.0035, +0.0212] | Supported |
| DCRG without protocol actors | -0.0005 | [-0.0032, +0.0016] | Not supported |

This supports a **guard-aware typed DCRG** contribution under the oracle assumption. It does
not support claiming that authorizing-EOA, EntryPoint, or protocol-actor features themselves
improve prediction. Those features require the real post-cutoff authority/delegate population.

## Uncertain-label sensitivity

The direction of full-DCRG minus untyped-guards remains positive when every uncertain item is
assigned bounded-negative (+0.0122) or UNSAFE (+0.0088). The capability-only comparison is not
robust: it changes from +0.0152 when all uncertain items are UNSAFE to -0.0071 when all are
bounded-negative. Protocol-actor removal remains essentially neutral under both extremes.

These extreme assignments are sensitivity point estimates, not confidence intervals.

## Selective-policy failure

The current `WARN` / `LOW_OBSERVED_RISK` / `DEFER` policy is not acceptable under the proxy
labels:

- Mean deferral rate: 33.6%.
- Mean warning recall: 47.3%.
- Mean low-observed-risk assignments: 27.7 per seed.
- Mean proxy-UNSAFE items assigned low observed risk: **14.0 per seed**.
- Proxy-positive rate inside low observed risk: **50.5%**.

Even an oracle threshold search over complete-coverage items finds only 0--2 binary items per
seed that can be assigned low risk before encountering an UNSAFE proxy item. A useful low-risk
region therefore does not appear to exist in this proxy population. The current high-risk
threshold cannot simultaneously serve as a low-risk certification threshold.

## End-state decision

If these labels were accepted literally as human labels, the project would have one promising
empirical contribution but not the three strong contributions currently targeted:

1. **Guard-aware DCRG:** provisionally supported, with modest but paired-positive improvement
   over capability-only and untyped representations.
2. **Coverage-gated low-risk policy:** empirically fails and must be redesigned or reduced to a
   `WARN`/`DEFER` analyst-triage contract.
3. **Authority-relative/provenance evaluation:** infrastructure exists, but authority-specific
   predictive value and post-cutoff semantic validity remain unestablished.

Therefore the project should not be declared finished under this assumption. The result is
strong enough to justify completing independent review, but only after choosing one of two
paths:

- **Narrow paper:** center DCRG, drop fusion superiority and low-risk claims, present selective
  behavior and actor ablations as negative findings, and complete independent labels.
- **Stronger paper:** redesign the decision contract using development data only, evaluate
  authority-relative features on the frozen post-cutoff pairs, then use a new untouched human
  test population because these proxy labels have now informed method decisions.

Machine-readable result:
`results/what_if_current_labels_as_human/current_label_oracle_what_if.json`.
