# Introduction, Motivation, Problem Formulation, Threat Model

## Introduction

EIP-7702 (finalized as part of Ethereum's Pectra upgrade) allows an externally-owned account
(EOA) to designate a "delegate" smart contract whose code the EOA will execute as if it were
its own, without giving up control of its private key. This is the technical foundation for a
wave of account-abstraction wallets (Sections 3 and this pass's `revision_v3/external_controls/`
document 8 such deployed projects, e.g. MetaMask's StatelessDeleGator, Coinbase's
EIP7702Proxy, ZeroDev's Kernel). The same mechanism that enables this legitimate
functionality also creates a new authorization-time attack surface: an EOA holder who signs
an authorization for a malicious or merely poorly-written delegate hands that delegate the
same practical capability over their assets and identity as their own private key.

## Motivation

Prior EIP-7702 studies detect malicious activity using transaction history, large-scale
cross-chain filtering, decompilation, and targeted rules. We study a different decision point:
local screening of a proposed delegate before authorization, when the delegate bytecode may be
the only available evidence. The natural deeper mitigations — full source verification, manual
audit, and service-backed decompilation — are too dependent on external services or specialized
expertise to serve as the only inline wallet response (see
`revision_v3/reports/ML_VS_STATIC_ANALYSIS_POSITIONING.md` for measured evidence: this
project's own semantic-evidence pipeline took seconds-to-tens-of-seconds per item and needed
4 independent external services). A fast, calibrated triage signal that can run locally,
with well-understood failure modes and an explicit escalation path to deeper analysis, fills
a gap the existing tooling landscape does not.

## Problem formulation

Given the runtime bytecode of a delegate contract $D$ proposed for EIP-7702 authorization by
account $A$, predict whether authorizing $D$ exposes $A$ to a concrete, exploitable
authorization-specific risk (arbitrary asset movement, arbitrary external call, unrestricted
initialization/upgrade, or an authorization-mechanism-specific flaw such as tx.origin-based
gating — see `revision_v3/human_eval/LLM_PROVISIONAL_LABELING_PROTOCOL.md`'s taxonomy) versus
showing low observed risk under the bounded evidence available. This is framed as a three-class
problem at labeling time (NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND / UNSAFE / INDETERMINATE) collapsed
to bounded-negative-vs-UNSAFE for model evaluation, with `INDETERMINATE` and
`NOT_BYTECODE_SCREENABLE` items explicitly excluded rather than forced into a binary label.

## Threat model

- **In scope**: a delegate contract whose bytecode is inspectable pre-authorization (the
  common case — the delegate address is known before the EOA signs).
- **Out of scope**: attacks that depend on delegate behavior that only manifests under
  specific, unobservable runtime state (flagged explicitly as `DYNAMIC_OR_STATE_DEPENDENT` /
  `EXTERNAL_DEPENDENCY` in the labeling taxonomy rather than silently assumed
  safe); social-engineering attacks that trick a user into authorizing a delegate address
  they did not intend to (a UI/UX problem, not a bytecode-safety problem); and compromise of
  the EOA's private key itself (EIP-7702 does not change this threat).
- **Adversary model**: the delegate contract's author is potentially adversarial and may
  deliberately construct bytecode that defeats naive selector-name or capability-presence
  heuristics (a design principle carried through this project's evidence pipeline: hard
  rules explicitly forbid concluding UNSAFE or the bounded-negative category from selector or
  capability presence alone
  — see the labeling protocol's "hard rules" section).

## Target contributions and validation condition

Subject to adjudicated human labels, this work targets three contributions: (1) a leakage-reduced,
temporally separated evaluation resource; (2) DCRG, a coverage-audited guard-aware EIP-7702
representation connecting reachable capabilities, authorization evidence, and analysis gaps; and
(3) a warning/no-model-warning/defer evaluation over family-held post-cutoff cases, legitimate
projects, real authority/delegate pairs, calibration, and paired uncertainty. The frozen
development-label analysis validates the implementation but does not satisfy the independent
method-superiority condition.
