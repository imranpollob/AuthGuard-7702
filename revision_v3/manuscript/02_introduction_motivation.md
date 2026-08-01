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

No wallet UI at authorization time currently evaluates delegate-contract safety
automatically. The natural mitigations — full source verification, manual audit, formal
decompilation — are each too slow, too dependent on external services, or too specialized to
run inline with a wallet's authorization flow (see
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
appearing safe to authorize under the evidence available. This is framed as a three-class
problem at labeling time (SAFE / UNSAFE / UNCERTAIN) collapsed to binary SAFE-vs-UNSAFE for
model evaluation, with UNCERTAIN items explicitly excluded rather than forced into a binary
label.

## Threat model

- **In scope**: a delegate contract whose bytecode is inspectable pre-authorization (the
  common case — the delegate address is known before the EOA signs).
- **Out of scope**: attacks that depend on delegate behavior that only manifests under
  specific, unobservable runtime state (flagged explicitly as `STATE_DEPENDENT_BEHAVIOR` /
  `EXTERNAL_OR_DYNAMIC_DEPENDENCY` in the labeling taxonomy rather than silently assumed
  safe); social-engineering attacks that trick a user into authorizing a delegate address
  they did not intend to (a UI/UX problem, not a bytecode-safety problem); and compromise of
  the EOA's private key itself (EIP-7702 does not change this threat).
- **Adversary model**: the delegate contract's author is potentially adversarial and may
  deliberately construct bytecode that defeats naive selector-name or capability-presence
  heuristics (a design principle carried through this project's evidence pipeline: hard
  rules explicitly forbid concluding UNSAFE/SAFE from selector or capability presence alone
  — see the labeling protocol's "hard rules" section).
