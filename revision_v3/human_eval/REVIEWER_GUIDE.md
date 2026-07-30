# Reviewer Guide — EIP-7702 Delegate Security Review

**You do not need to already know what EIP-7702 is, understand smart-contract security, or
know how the AuthGuard-7702 machine-learning model works.** This guide explains everything you
need from scratch. Read it once before your first review; keep it open as a reference while
you work.

---

## 1. Background: what you're actually looking at

### 1.1 What is an externally owned account (EOA)?

On Ethereum (and similar blockchains), there are two kinds of accounts:

- **Externally owned accounts (EOAs)** — controlled by a private key, the kind of account a
  normal wallet (MetaMask, etc.) gives you. An EOA cannot run its own code; it can only send
  transactions.
- **Contract accounts** — controlled by code that was deployed to the chain. A contract can
  hold assets and run arbitrary logic when called.

Historically, an EOA could never "have code" — it was always just a key pair, nothing more.

### 1.2 What does EIP-7702 change?

EIP-7702 (live on Ethereum and several other chains since mid-2025) lets an EOA **temporarily
or persistently point at a piece of contract code**, called a **delegate**. The EOA's owner
signs an **authorization** — a message saying "let my account run the code found at this other
address." Once authorized, transactions to the EOA execute that delegate's code, but — and
this is the critical part — **the code runs using the EOA's own storage, balance, and
identity**, not the delegate contract's. This is what makes EIP-7702 useful: it lets a plain
EOA gain smart-account features (batched transactions, gas sponsorship, spending limits,
session keys, etc.) without changing the account's address.

### 1.3 What is a "delegate contract"?

The delegate is just an ordinary smart contract, deployed once, whose *code* many different
EOAs can point at. It was not necessarily written with EIP-7702 in mind — some delegates are
purpose-built smart-account frameworks (from wallet companies); a delegate could in principle
be anything already sitting on chain.

### 1.4 What does "authorization" mean in practice?

The EOA owner cryptographically signs a message naming the delegate's address (and a chain ID
and nonce). That signature is submitted on-chain in a special transaction type. After it's
processed, the EOA's account now "points at" that delegate's code.

### 1.5 Why does the delegate execute *in the user's account context*?

This is the single most important fact for this review. When code runs "in the account's
context," it means:
- `msg.sender` checks inside the delegate can see calls as if they came from the EOA itself.
- The delegate's `SLOAD`/`SSTORE` (storage read/write) operations read and write the **EOA's**
  storage, not some separate storage the delegate contract owns elsewhere.
- Any `CALL` the delegate code makes that moves ETH or tokens moves the **EOA's** ETH or
  tokens.
- Any token `approve()` the delegate code executes grants approval **from the EOA**.

The delegate's code is essentially "borrowed" and run as if it were the EOA's own code.

### 1.6 Why can a dangerous delegate affect assets, approvals, storage, and permissions?

Because of 1.5: **whatever the delegate's code can do, it does using the EOA's own assets and
permissions.** If the delegate code contains a path that lets an unauthorized third party (not
the EOA owner) trigger an arbitrary token transfer, or grant an approval to an address the
attacker controls, or overwrite an "owner" storage slot, then *that EOA's* funds are at risk —
not the delegate contract's own funds (a delegate contract typically holds nothing itself; it's
a template of logic).

### 1.7 Legitimate smart-account implementation vs. malicious/unsafe delegate

A **legitimate** delegate implementation (the kind wallet companies build) is carefully
designed so that every sensitive action — moving assets, changing owners, approving tokens —
is gated behind a check that the caller is the account owner (or someone the owner explicitly
authorized, like a session key with limited scope). A **malicious or unsafe** delegate is one
where that gate is missing, bypassable, or was never implemented for a sensitive action — so
*anyone*, not just the account owner, can trigger it.

### 1.8 Concrete vulnerability vs. uncertain/unresolved case

- A **concrete vulnerability** is something you can point to in the evidence: "this function
  transfers tokens and has no caller check" or "this initializer sets the owner and can be
  called by anyone, at any time, including after deployment."
- An **uncertain/unresolved case** is one where you genuinely cannot tell from the available
  evidence — e.g., the contract is a proxy and you don't know what the real implementation
  does, or the dangerous-looking function's behavior depends on some external contract's state
  that isn't available to inspect.

**Do not guess.** If you can't tell, the correct answer is UNCERTAIN, not a guess at SAFE or
UNSAFE.

---

## 2. Worked example

- Alice owns an ordinary wallet (an EOA).
- Alice authorizes delegate contract **D** (perhaps to get batched transactions or gas
  sponsorship from a wallet app she trusts).
- **D** can now execute delegated logic in Alice's account context (per §1.5–1.6).
- **If D allows an attacker to choose arbitrary targets, calldata, token approvals, or
  ownership settings, Alice's assets may be exposed** — because that logic runs as Alice,
  with Alice's balance and Alice's approvals.
- **Therefore, the review question is not only whether D contains an external call.** Nearly
  every smart-account delegate contains external calls — that's the whole point, so the
  account owner can *use* the delegate to interact with other contracts.
- **The question is whether an unauthorized party can misuse D after Alice authorizes it** —
  i.e., can someone who is *not* Alice (and not someone Alice explicitly permitted) trigger
  D's sensitive capabilities?

---

## 3. Review checklist

Work through these steps **in order** for every item. Each evidence column in the Excel sheet
is labeled to match a section below.

### A. Identify the contract
- Is this an actual runtime implementation, or just a delegation designator / proxy pointer?
- Can the real implementation be resolved (i.e., do you know what code actually executes)?
- Is the contract associated with a documented project?
- Is verified source code available?

### B. Identify who controls the contract
- Is there an owner or administrator concept at all?
- How is the owner initialized — at deployment, via a separate call, or never explicitly?
- Can an arbitrary caller initialize or replace the owner?
- Is access control (an owner/permission check) applied to sensitive functions?
- Can authority remain unset, or become the zero address (effectively "nobody," which can be
  as dangerous as "anybody" depending on the logic)?
- Can an attacker obtain privileged control through some path?

### C. Inspect external-call capabilities
- Can the contract execute `CALL`, `DELEGATECALL`, or otherwise run attacker-supplied calldata?
- Who chooses the **target address** of that call — the owner, or anyone?
- Who chooses the **value** sent?
- Who chooses the **calldata**?
- Is the capability restricted to the authorized account owner (or an explicitly permitted
  party), or can an unauthorized caller trigger it?

### D. Inspect asset-related behavior
- Can the contract transfer ETH?
- Can it transfer ERC-20 or ERC-721 assets?
- Can it create token approvals (`approve`, `permit`, or similar)?
- Can it call `transferFrom` or equivalent?
- Are these actions restricted appropriately (owner-only), or open?

### E. Inspect initialization risks
- Does the implementation expect a constructor that *will not run* when used through EIP-7702
  (since the code is never actually "deployed" fresh by the EOA — it's borrowed)?
- Is there a separate `initialize()`-style function instead?
- Can someone other than the account owner invoke that initializer?
- Can the account remain uninitialized indefinitely?
- Can an attacker call the initializer *first*, before the legitimate owner does, and set
  themselves as the privileged party? (This is a well-known real-world proxy/initializer
  attack pattern.)

### F. Inspect proxy and upgrade risks
- Does the contract delegate to another implementation address?
- Is that implementation address known/resolvable?
- Can the implementation be changed after the fact (upgradeability)?
- Who controls upgrades?
- **If the actual behavior cannot be resolved (e.g., the real implementation isn't available
  to inspect), choose UNCERTAIN rather than guessing.**

### G. Inspect EIP-7702 suitability
- Was the contract actually designed for use as an EIP-7702 delegate, or does it look like an
  ordinary contract that happens to be pointed at?
- Does it assume ordinary deployment / constructor-based initialization (a red flag for 7702
  use, per §E)?
- Is its authorization behavior documented anywhere?
- Is it a known smart-account implementation (check the "documented project" evidence field)?
- Does the project's documentation match what's actually in the deployed bytecode, as far as
  you can tell?

### H. Make the decision

- Choose **UNSAFE** only when there is a **concrete** dangerous behavior or security condition
  you can point to in the evidence.
- Choose **SAFE** when the available evidence reasonably supports appropriate authorization
  behavior and no concrete dangerous path was found.
- Choose **UNCERTAIN** when the evidence is incomplete, ambiguous, dynamically dependent, or
  not fully inspectable from what's provided.

### Important warnings — read these twice

- **The presence of `CALL` or `DELEGATECALL` alone does not make a contract unsafe.** Nearly
  every legitimate smart-account delegate has these.
- **A fallback or receive function alone does not make a contract unsafe.** These are normal
  and common.
- **An unverified contract is not automatically unsafe.** Lack of verification is a gap in
  evidence, not proof of danger — it may push you toward UNCERTAIN if it prevents you from
  confirming access control, but it isn't itself a finding.
- **A documented project is not automatically safe.** Documentation existing doesn't prove the
  deployed bytecode matches it, or that the implementation has no bugs.
- **A high number of authorizations (popularity) is not proof of safety.**
- **A model or LLM prediction is not ground truth.** The LLM's preliminary review (provided in
  your sheet) is a starting point to check, not an answer to copy. You are expected to
  independently verify or challenge it.
- **When evidence is insufficient, choose UNCERTAIN.** There is no penalty for UNCERTAIN — it
  is often the *correct* answer, not a cop-out.

---

## 4. Educational examples

These are **synthetic, illustrative examples only** — they do not correspond to any real item
in the Pilot, Gold-Dev, or Gold-Test sets. They exist purely to calibrate your judgment.

### Example 1 — SAFE: documented smart account with owner-only execution

**Evidence**: Bytecode matches a well-known smart-account framework's published source. Every
function that performs a `CALL` or asset transfer checks `msg.sender == owner` (or a validated
signature from the owner) before proceeding. The owner is set once, at initialization, by the
deploying account, and cannot be reassigned except through an owner-gated function.

**Correct label**: SAFE. **Reason**: `DOCUMENTED_LEGITIMATE_IMPLEMENTATION` /
`ACCESS_CONTROL_APPEARS_APPROPRIATE`.

**Common incorrect interpretation**: Marking it UNSAFE just because it *contains* `CALL` and
`DELEGATECALL` opcodes. Their presence is expected — the question is who can trigger them.

### Example 2 — UNSAFE: arbitrary call available to any caller

**Evidence**: A function `execute(address target, uint256 value, bytes calldata data)` performs
`target.call{value: value}(data)` with **no caller check at all** — any address can call
`execute` and make the account perform any call, with any value, to any target.

**Correct label**: UNSAFE. **Reason**: `ARBITRARY_EXTERNAL_CALL` (or
`UNAUTHORIZED_ASSET_MOVEMENT` if the call can move ETH, which it can here).

**Common incorrect interpretation**: Assuming an `execute`-style function is inherently fine
because "that's what smart accounts do." The *pattern* is normal; the *missing access control*
is the concrete problem.

### Example 3 — UNSAFE: initialization takeover

**Evidence**: The contract has an `initialize(address owner)` function instead of a
constructor (expected for 7702 delegates, per §E). It sets `owner = msg.sender`. Nothing
prevents it from being called more than once, or by anyone, at any time after the EOA starts
using the delegate — including by an attacker who front-runs the legitimate owner's first
interaction.

**Correct label**: UNSAFE. **Reason**: `UNSAFE_INITIALIZATION` (and/or
`OWNER_OR_PRIVILEGE_TAKEOVER`).

**Common incorrect interpretation**: Assuming any `initialize()` function is fine because
"that's the normal proxy pattern." The normal pattern also requires a guard (e.g., an
`initialized` flag, or restricting the call to a known factory) — check for that guard
specifically.

### Example 4 — UNSAFE: unrestricted token approval

**Evidence**: A function lets any caller specify a token address and a spender address, then
calls `IERC20(token).approve(spender, type(uint256).max)` with no restriction on who can call
it or which spender is allowed.

**Correct label**: UNSAFE. **Reason**: `DANGEROUS_APPROVAL_OR_TRANSFER`.

**Common incorrect interpretation**: Waiting to see an actual `transferFrom` drain before
flagging it. The *approval* itself is the dangerous capability — once granted to an attacker's
address, funds can be drained at any later time, by the attacker, independent of this
contract.

### Example 5 — UNCERTAIN: unresolved proxy implementation

**Evidence**: The contract is a minimal proxy that `DELEGATECALL`s to an implementation address
read from storage. The implementation address is not a fixed, known constant — it depends on a
storage slot whose current value could not be resolved from the bytecode alone (would require
live on-chain state that wasn't available in this evidence packet).

**Correct label**: UNCERTAIN. **Reason**: `UNRESOLVED_PROXY`.

**Common incorrect interpretation**: Defaulting to SAFE because "proxies are a standard,
legitimate pattern," or defaulting to UNSAFE because "we can't see what it does." Neither
guess is supported — the honest answer is that the real implementation's behavior is unknown.

### Example 6 — UNCERTAIN: behavior depending on unavailable external state

**Evidence**: A function's effect depends on the return value of a call to another external
contract (e.g., a price oracle or a registry) whose current state and logic were not part of
the evidence packet — the safety of the function genuinely depends on what that external
contract currently does, which cannot be determined from this delegate's bytecode alone.

**Correct label**: UNCERTAIN. **Reason**: `EXTERNAL_OR_DYNAMIC_DEPENDENCY` (or
`STATE_DEPENDENT_BEHAVIOR`).

**Common incorrect interpretation**: Assuming the external dependency is trustworthy (→ SAFE)
or assuming any external dependency is inherently a red flag (→ UNSAFE). Both are guesses
without inspecting the dependency.

---

## 5. A note on the LLM's preliminary review

Every item you review comes with a preliminary analysis generated by an AI assistant. It was
explicitly **not** given the AuthGuard model's score or prediction, the source-analyzer's
label, or any information about whether this item is currently a model success or failure —
its analysis is based only on the same bytecode-derived evidence you have. Treat it as a
first draft made by a knowledgeable but fallible colleague: read it, check its claims against
the evidence yourself, and record whether you agree, partly agree, or disagree — and why. Your
independent judgment is what matters; the LLM review exists to save you time, not to replace
your analysis.
