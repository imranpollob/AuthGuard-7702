# Opus 5 Labeling — Project Context Summary

**LABEL_SOURCE=LLM_PROVISIONAL_OPUS5 · STATIC_ANALYZER_EVIDENCE=VISIBLE ·
STATUS=PROVISIONAL_PENDING_HUMAN_REVIEW**

Written before any label was assigned, from the repository materials listed in §8. Its purpose
is to make explicit what the labeler understood about the mechanism, the threat model, the
label pipeline, and the limits of the evidence — so that a human reviewer can check the
*premises* of the labels, not only the labels.

---

## 1. What EIP-7702 authorization does

EIP-7702 (Ethereum, Pectra) lets an externally-owned account (EOA) sign an **authorization
tuple** `(chain_id, delegate_address, nonce)`. Once that authorization is included on chain,
the EOA's account entry carries a **delegation designator** `0xef0100 || delegate_address`,
and every subsequent call to the EOA executes the delegate's runtime code. The EOA keeps its
private key, its address, its balance, and its nonce. Authorization is revocable by signing a
new authorization for the zero address.

The signature commits only to the delegate's **address**. It does not commit to the delegate's
code, so it does not commit to the delegate's behaviour: if the delegate address is itself a
proxy, or is a contract whose behaviour depends on mutable storage, the authorizer is trusting
something they did not sign over. This is why implementation resolution (§ evidence C) is a
first-class part of the review and not a formality.

## 2. What delegate code can do in the EOA's context

The delegate's code executes **with the EOA's storage, balance, and identity**:

| Operation in the delegate | Effect once the EOA has authorized |
|---|---|
| `SLOAD` / `SSTORE` | reads/writes the **EOA's** storage, which starts empty and is shared by every delegate the EOA ever points at |
| `CALL` with value | spends the **EOA's** ETH |
| `CALL` to an ERC-20 `transfer`/`approve` | moves or approves the **EOA's** tokens |
| `DELEGATECALL` | runs a third contract's code against the **EOA's** storage |
| `ADDRESS()` | returns the **EOA's** address, not the delegate's |
| `CALLER()` | the account that called the EOA |
| `SELFDESTRUCT` | (post-Cancun) sends the **EOA's** balance to the beneficiary |

Two consequences drive the whole review:

1. **Constructors do not run.** The delegate was constructed once, at its own address, with
   its own storage. When an EOA borrows the code, none of that constructor state exists in the
   EOA's storage. Anything the contract's design assumes was set at construction (an owner, an
   `initialized` flag, an immutable-emulating storage slot) is **zero** in the EOA's context
   until something explicitly sets it. This makes initializer-takeover the signature EIP-7702
   failure mode rather than a generic proxy concern.
2. **`ADDRESS() == CALLER()` means something different here.** In a normal contract that test
   only passes for a re-entrant self-call. Under EIP-7702 it is the canonical way a smart
   account says "only I, the account owner, sending a transaction from my own EOA, may do
   this" — because a transaction the EOA sends to itself has `msg.sender == address(this) ==
   the EOA`. A `self_call_check` is therefore *positive* authorization evidence in this
   setting, not a curiosity.

## 3. Threat model used for these labels

Taken from `revision_v3/manuscript/02_introduction_motivation.md` and
`revision_v3/human_eval/REVIEWER_GUIDE.md`.

- **Question asked**: given the delegate's runtime bytecode, would authorizing it expose the
  authorizing EOA to a concrete, exploitable authorization-specific risk?
- **Adversary**: anyone who is *not* the authorizing account owner (and not a party the owner
  explicitly delegated to), able to send transactions to the EOA after authorization. The
  delegate author may also be adversarial and may deliberately defeat naive
  selector-name/capability heuristics.
- **In scope**: bytecode inspectable before authorization; unauthorized asset movement,
  approval, arbitrary call, ownership/initializer takeover, unauthorized upgrade or
  delegatecall, destructive operations, authorization-mechanism-specific flaws.
- **Out of scope**: private-key compromise (EIP-7702 does not change it); social engineering
  about *which* address to authorize (a UI problem); behaviour that only manifests under
  unobservable runtime state (labeled `STATE_DEPENDENT_BEHAVIOR` /
  `EXTERNAL_OR_DYNAMIC_DEPENDENCY`, not assumed safe).

## 4. Capability vs. vulnerability — the distinction these labels turn on

A **capability** is the presence of a powerful operation: a `CALL`, a `DELEGATECALL`, a
`CREATE2`, an `approve` selector, a `fallback`. Essentially every legitimate smart-account
delegate has all of these; that is the entire point of the delegate.

A **vulnerability** is a capability an *unauthorized* party can reach. Formally, the property
that matters is not "does a sensitive opcode exist" but:

> does there exist a path from an externally reachable entry point to a sensitive operation
> that does **not** pass through an authorization check?

That is a control-flow *dominance* question, and it is the question this pass's analyzer
answers directly (§6). The distinction is the reason the previous provisional pass produced
87% UNSAFE: it was, in effect, measuring capability.

## 5. What the original source analyzer detects — precisely

The `source_label` column in every manifest comes from the USENIX EIP-7702 study artifact's
`eoa_detect` pipeline (`USENIX EIP-7702 artifact/eoa_detect/`), which decompiles each address
with **Gigahorse** and evaluates **Soufflé/Datalog** rules in
`eoa_detect/decompile/analyze.dl`. The operative rule is:

```datalog
AM_Analysis_ExternalCallInfo(func, callStmt, callOp, calleeVar, numArg, numRet) :-
  PublicFunctionSelector(func, _),
  AM_Statement_Function(callStmt, func),
  (CALL(callStmt, ...); DELEGATECALL(callStmt, ...)),
  ...
```

with `AM_Statement_Function` closed transitively over `CallGraphEdge`, i.e. **interprocedural
reachability**. Verified against the shipped `detect_result.jsonl`: 793 addresses, 866 tuples,
and **every single tuple's enclosing function is `receive()` (765) or `fallback()` (101)** —
no other enclosing function appears. 822/866 call sites resolve to `UnkownCall`; the remainder
are ordinary selectors (`transfer`, `withdraw`, `approve`, `deposit`, …).

So, stated exactly:

> **source_label = positive ⟺ the decompiled code has an external `CALL`/`DELEGATECALL`
> reachable from `receive()` or `fallback()`.**

What this means for labeling:

- **The rule contains no authorization predicate whatsoever.** `analyze.dl` never references
  `guards.dl`'s guard relations in this rule despite including the header. A positive says
  *"a powerful operation is reachable from an entry point that carries no dispatch-time caller
  check"* — genuinely relevant evidence, and stronger than a bare opcode census, but it is a
  **reachability** finding, not a *missing-access-control* finding. A guard inside the
  reachable path does not clear the rule.
- **`unflagged` is weak.** It means only that this one pattern did not fire. It can mean the
  contract has no `receive`/`fallback`, that Gigahorse failed to decompile it, that the
  sensitive operation sits behind a normal selector instead, or that the address was outside
  the analysed pool. `revision_v2/audit/DATASET_AUDIT_REPORT.md` states this plainly: the
  negatives are *rule-silent* delegates and **"no benignity verification of any kind exists"**.
- **The second shipped rule is lexical.** `AM_Detect_SensitiveSigName` matches function-name
  prefixes (`attack`, `hack`, `sweep`, `steal`, `drain`, `exploit`, `pwn`), firing on 58/793
  positives. Name-based, and trivially evaded.
- **The pipeline was never re-executed here.** `revision_v2/results/gigahorse/feasibility.md`
  records that Soufflé and the Gigahorse `clientlib/*.dl` are not available in this
  environment. Everything above is read from the artifact's *shipped intermediate outputs*.
  Per-item rule facts are therefore available only for the 718 addresses the artifact ships
  them for.

Because of all this, the instruction's rule — *items supported only by
`SOURCE_RULE_ONLY_SUPPORT` should normally be UNCERTAIN, not UNSAFE* — is not a stylistic
preference. It follows from what the rule provably computes.

## 6. What AuthGuard predicts (and why its item-level output is withheld here)

AuthGuard is a compact neural classifier (`authguard_sequence_dense`, 97,646 parameters) over
**raw runtime bytecode**, trained on the v2 benchmark whose positive class is defined by the
source rule above. `revision_v2/audit/DATASET_AUDIT_REPORT.md` Part 2 states the central
finding without hedging: **"the model is learning to reproduce the source detector"** — the
positive label is a deterministic function of the bytecode the model receives. The defensible
framing is *analyzer surrogate / fast triage*, not independent vulnerability detection.

Its per-item score is **withheld from this labeling pass** and from the evidence dossiers by
construction (`build_dossiers.py` never reads `ref_model_mean_score`, `gold_dev_stratum`,
`pilot_reason`, or any results file). AuthGuard's predictions are the thing being evaluated;
feeding them in would make the evaluation circular a second time. The *architecture and task*
are documented here, which is permitted and necessary context; the *item-level decision* is
not.

## 7. How the current datasets were constructed

From `revision_v3/human_eval/SAMPLING_PROTOCOL.md`, seed 770220262, sampling unit = unique
exact runtime bytecode:

- **Gold-Test (150)** built first, population-proportional by source label (50 positive / 100
  unflagged), **never using model score**, max 3 bytecodes per family, frozen immediately
  (`gold_test_hashes.json`). 126 distinct families, 7 chains.
- **Gold-Dev (60)** built next, excluding Gold-Test's families entirely; deliberately
  stratified by source label × model score. Includes a documented shortfall: only 5
  `positive_low_score` items existed after exclusion, backfilled with 10
  `unflagged_high_score_backfill` items rather than under-delivering.
- **Pilot (20)** built last, excluding both by exact bytecode; 7 source-positive, 7
  source-unflagged, 6 model/source disagreements.

Underlying population (`revision_v2/data/authguardbench_7702_v2.csv.gz`, PRIMARY_EVALUATION):
2,190 rows, 727 positive, 1,463 negative, 790 families. Positives are the USENIX rule hits;
`benign_cleared` negatives are the rule-silent complement of the same observed-delegate pool.

**None of these manifests were read for anything other than identity and bytecode in this
pass, and none were modified.** Frozen hashes re-verified.

## 8. Materials read before labeling

`revision_v3/manuscript/` (all 9 files, notably 02 threat model, 03 dataset/labels, 06
provisional results); `revision_v3/human_eval/REVIEWER_GUIDE.md`;
`LLM_PROVISIONAL_LABELING_PROTOCOL.md`; `SAMPLING_PROTOCOL.md`; `taxonomy.py`;
`revision_v3/reports/PARALLEL_PIPELINE_COMPLETION_REPORT.md`, `PILOT_CODE_EVIDENCE_REPORT.md`,
`LEGITIMATE_CONTROL_VERIFICATION_REPORT.md`, `TEMPORAL_COLLECTION_FINAL_STATUS.md`,
`ML_VS_STATIC_ANALYSIS_POSITIONING.md`; `revision_v2/audit/DATASET_AUDIT_REPORT.md`;
`revision_v2/results/gigahorse/feasibility.md`; `USENIX EIP-7702 artifact/` (`README.md`,
`eoa_detect/decompile/analyze.dl`, `eoa_detect/detect_result.jsonl`);
`revision_v3/experiments/excel_review/evidence_pipeline.py`,
`generate_provisional_labels.py`; the three sampling manifests; the three existing
`results/llm_provisional/*_labels.json`; `revision_v3/external_controls/`.

## 9. Limitations of decompilation and automated guard tracing

**These bound every label produced in this pass.**

### 9.1 The previous pass's guard tracer was a linear byte-window scan

`evidence_pipeline.trace_guards` classifies a dispatched function by scanning the contiguous
byte range between its dispatch offset and the next one, looking for
`CALLER|ORIGIN … EQ … JUMPI` within an 8-instruction lookahead. It cannot follow a single
jump. It therefore structurally cannot see: guards compiled into shared internal helpers
(which is what a Solidity `modifier` becomes, usually placed far from the caller's byte
range); signature authorization via `ecrecover`; storage-based permission checks; or whether
the sensitive opcode it is worried about is even reachable from that entry.

Its `OPEN` means **"no recognized guard pattern in this byte window"** — which is
`INCOMPLETE_GUARD_EVIDENCE`, not "no access control". It produced `OPEN_FOUND` for 50/60
Gold-Dev and 140/150 Gold-Test items. This is the primary mechanical explanation for the
previous pass's 87% UNSAFE rate, and it is why this pass does not reuse it.

### 9.2 What replaced it, and what that still cannot do

`revision_v3/experiments/opus5_labeling/evm_cfg.py` implements a real disassembler, basic-block
CFG, and a bounded symbolic-stack executor that resolves dynamic `JUMP` targets (so internal
calls *and* returns are followed) while tracking value provenance
(`calldata`/`caller`/`origin`/`address`/`sload`/`ecrecover`/`callvalue`/const). A `JUMPI` whose
**condition** is tainted by an authorization source is a guard. A sensitive operation is
reported `UNGUARDED_PATH` only if it remains reachable from the entry when traversal is cut at
every guard — a genuine *"there exists an unauthenticated path"* claim rather than an
absence-of-pattern claim. It also re-derives the source rule's own question locally, by seeding
a non-matching selector so traversal deterministically takes the `receive()`/`fallback()` path.

Residual limitations, all recorded per item rather than assumed away:

- **Unresolved dynamic jumps.** Jump tables, jumps whose target is computed, and returns whose
  address was merged away leave edges unexplored. Every item records
  `unresolved_dynamic_jumps`; any nonzero value means the reachability result is a *lower
  bound* on what is reachable, so `UNGUARDED_PATH` stays sound but `GUARD_DOMINATED` weakens
  toward UNCERTAIN.
- **State-key merging.** Visited states are keyed on the top 8 stack values; deeper
  distinctions are merged, which can over-approximate reachability (conservative) or
  mis-resolve an internal return (unsound in either direction). Bounded at 24,000 states;
  `hit_state_cap` is recorded.
- **Guard *strength* is not verified.** The analyzer proves a branch's condition depends on
  `CALLER`/`ORIGIN`/`ecrecover`/storage. It does **not** prove the branch reverts on failure
  rather than merely selecting a different path, nor that the value compared against is the
  right one. A `tx.origin`-based guard is detected as a guard and must then be judged
  *semantically* — which is exactly the LLM's job, not the tracer's.
- **Storage-derived conditions are ambiguous by nature.** An `SLOAD`-conditioned branch may be
  an owner check, an `initialized` flag, a paused flag, or a balance test. These are reported
  separately (`GUARDED_BY_STORAGE_CONDITION`) and never silently counted as authorization.
- **Decompilation is partial.** Only 6/60 Gold-Dev and 18/150 Gold-Test items have verified
  source; the rest are judged from bytecode alone. `evmole` recovers dispatched selectors, but
  atypical dispatchers yield none, in which case the whole program is analysed from `pc=0`.
  4byte.directory resolves many but not all selectors, and a resolved name is a *hint*, never
  evidence of behaviour.
- **Proxies bound everything.** Where the executing implementation is a storage-held address,
  the delegate's real behaviour is whatever that implementation currently does — and it can
  change after authorization. Unresolved implementation ⇒ `UNCERTAIN/UNRESOLVED_PROXY`, never
  a guess in either direction.
- **On-chain state is a snapshot.** Storage values, verification status, and implementation
  pointers were read live during the previous pass (2026-07-30/31) and are reused here. They
  can change; a delegate that is safe today can be upgraded tomorrow.

### 9.3 Consequence for how these labels should be read

Every label in this pass is a judgement over *bytecode-derived evidence about a specific
snapshot*, produced by a language model with the static analyzer's verdict visible. Because
the analyzer's verdict was visible, **agreement between these labels and the source rule is
descriptive, not an independent evaluation of the rule** (see
`OPUS5_LABEL_QUALITY_REPORT.md` §static-analyzer limitation). They are provisional input to
human review, and they are replaced, not corroborated, by `human_final_label`.
