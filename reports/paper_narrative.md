# Paper Narrative (clean prose, no in-line file citations)

## 1. Problem
EIP-7702 lets an externally owned account install a delegate contract's code into its own
account; once the authorization is signed, that code executes with the account's full authority
over ETH, token allowances, and NFTs. The dangerous action is authorized by the signature
itself, so the only reliable defense point is *before* signing. A malicious delegate can be
freshly deployed with no transaction history, which defeats post-hoc, history-dependent
detection for the first victims. The information actually available at signing time is the
delegate's runtime bytecode. The task is thus: from bytecode alone, in interactive time, without
a decompiler, emit a risk score for a delegate the user is about to empower. This differs from
generic contract-vulnerability detection — the object of suspicion is code the signer is about to
grant authority over their own assets — and because attackers redeploy new families and mutate
bytecode between deployments, it is fundamentally a generalization-and-robustness problem.

## 2. Existing solutions
The only published EIP-7702 detector is post-hoc: it decompiles contracts that have already
appeared in attacks and applies a Datalog rule (external call reachable from a value-receiving
hook), corroborated by a fixed sensitive-name lexicon. Blocklists and exact bytecode signatures
catch only what has been seen. Opcode/bytecode phishing classifiers exist for other surfaces but
are rarely evaluated under family holdout; transaction- and graph-based detectors need on-chain
history and operate after the fact; heavyweight decompiler pipelines impose a deployment burden
incompatible with a signing hook (though we did not measure that runtime and treat it as a
deployment concern, not an established result).

## 3. Gap
Our experiments demonstrate three concrete gaps: exact-hash and signature methods fail on unseen
families (blocklist recall 0.000 under family holdout); random splits inflate reported accuracy
by memorizing near-duplicates (a ~0.10 AUPRC swing); and the deployed rule's discriminating
components are trivially evaded (a byte-level function rename drops the name-match to zero
detection). Prior EIP-7702 and phishing-bytecode work has not evaluated adversarial robustness at
all. What is missing is a pre-signing, bytecode-only screen evaluated under a leakage-safe
family-grouped protocol and stress-tested against structure-preserving evasion.

## 4. Our solution
AuthGuard-7702 fetches the delegate's runtime bytecode, disassembles it deterministically, and
extracts an opcode histogram, hashed opcode 4-grams, selector-set signals, and structural EVM
statistics — with tautological and split-identifying features (the two rule-restating capability
flags and the chain field) programmatically banned. A frozen, deterministic global clustering
assigns every contract a family so that identical or near-identical bytecode can never straddle a
split. A gradient-boosted classifier (AuthGuard-M0) is trained on original bytecode; a second
model (AuthGuard-aug) is trained on the same data augmented with source-balanced,
structure-preserving variants (metadata rewrite, address-immediate randomization, dead-code
flooding). Both fix their operating threshold on clean held-out validation only. At signing time
the model scores a contract in about 3.4 milliseconds with no decompiler in the loop. Augmented
training is preferable because it improves robustness to heavy dead-code flooding — recovering
held-out +200% recall from 0.624 to 0.790 — while slightly *raising* clean AUPRC (0.830 to 0.849)
and *lowering* the benign false-positive rate, and without learning a "padding-implies-malicious"
shortcut.

## 5. Contributions
(1) A decompiler-free, bytecode-only pre-signing risk screen for EIP-7702 delegates that attains
0.856 AUPRC under leave-family-out at 3.4 ms per contract. (2) A frozen, deterministic
family-grouped evaluation showing that random splits inflate AUPRC by roughly 0.10 and that
unseen-family evaluation is materially harder — with the blocklist's rise from 0.324 to 0.558
exposing the memorization mechanism. (3) A verified structure-preserving mutation benchmark and a
leakage-safe, source-balanced augmentation protocol that significantly improves robustness to a
held-out flooding severity (recall 0.624 to 0.790, 95% CI on the paired gain [0.131, 0.193]),
generalizes to singleton families (0.655 to 0.850), and does so without clean-data cost or a
padding shortcut — while candidly leaving a residual 27.5% false-positive rate under the heaviest
padding.

## 7. Evaluation (summary prose)
Under leave-family-out, AuthGuard reaches 0.856 AUPRC, ahead of opcode ensembles (0.789) and far
ahead of rule and blocklist baselines. A random split would have reported 0.961 — the gap we
attribute to near-duplicate leakage rather than generalization. Against structure-preserving
mutation, the sensitive-name approximation falls to zero detection under a rename and exact-hash
blocklisting is useless throughout, whereas the learned model degrades gracefully. Augmented
training then recovers most of the heavy-flooding loss on the held-out severity axis, with paired
bootstrap confidence intervals excluding zero, no clean-performance cost, and benign
false-positive rates that fall rather than rise — evidence against a padding shortcut. End-to-end
latency is 3.4 milliseconds.

## 8. Discussion (see discussion_draft.md for the full section)
The methodological spine is the evaluation discipline, not the estimator. The strongest
remaining weaknesses are label circularity (all positives are rule-derived), weak negatives
(rule-silent, up to ~8% contaminated), and that independent prospective sourcing yielded only one
confirmed novel delegate. Robustness is improved, not achieved: the compound worst case
(mutation plus heavy flooding together) was left untested by design to keep the mutation
condition held-out, and heavy padding still induces substantial benign false positives. We make
no claim about the full USENIX pipeline (not executed) and no decompiler speedup claim (not
measured).
