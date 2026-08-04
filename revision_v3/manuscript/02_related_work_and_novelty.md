# Related Work and Novelty Boundary

## EIP-7702 security measurement and rule-based detection

Huang et al., *Revealing the Dark Side of Smart Accounts* (USENIX Security 2026), is the
closest prior work and the provenance of the original analyzer-derived benchmark. It combines
seven-chain transaction filtering, Gigahorse decompilation, and rules matching standardized
reception hooks with reachable value-moving external calls; it reports 924 manually verified
malicious contracts. AuthGuard-7702 must therefore not claim the first EIP-7702 detector,
first cross-chain dataset, first use of bytecode static analysis, or first identification of
constructor/storage-context risks. That work is both the direct rule baseline and a source of
training-era families, never independent test data.

Qi et al., *EIP-7702 Phishing Attack* (arXiv:2512.12174, 2025), studies persistent delegation
phishing, three trigger pathways, ERC-4337-mediated activation, cross-chain authorization, and
large-scale authorization/execution events. It further rules out claims that this paper first
connects EIP-7702 with ERC-4337 or first measures delegation phishing. Our distinct question is
whether a wallet can screen delegate runtime bytecode *before authorization* when reputation,
history, and sometimes authorizing-account context are unavailable.

## Smart-contract graph and bytecode learning

Contract graphs, CFG/data-flow representations, and learned graph models are established prior
art, including Zhuang et al. (IJCAI 2020), SCGformer (IET Blockchain 2023), COBRA (ASE 2024),
and BugSweeper (AAAI 2026). Opcode-sequence learning and multi-view fusion are likewise not new.
The proposed DCRG claim is consequently narrower: an authority-relative, EIP-7702 execution
representation that types guards by what they authorize, connects them to reachable sensitive
capabilities, and records analysis gaps. A capability-only CFG, untyped guards, the Huang et al.
hook rule, sequence models, and full DCRG are required ablations/baselines.

## Selective prediction

Classification with a reject option and risk-coverage analysis are established, for example in
SelectiveNet (ICML 2019) and subsequent one-sided selective-classification work. We do not
claim a new selective-learning algorithm. The application contribution is a conservative
pre-authorization contract: `WARN`, `LOW_OBSERVED_RISK`, or `DEFER`, where incomplete semantic
coverage is structurally forbidden from producing a low-risk decision. Its value must be shown
through risk-coverage curves, low-risk error audits, and legitimate-deployment controls—not by
renaming ordinary classifier uncertainty.

## Defensible novelty statement

Subject to independent-label and post-cutoff validation, the paper's method novelty is the
combination of (i) authority-relative guard semantics for EIP-7702 delegate execution and
(ii) coverage-gated pre-authorization decisions. The benchmark contribution is a
provenance-audited evaluation of that question, not a claim to the first EIP-7702 attack
dataset. Generic CFG construction, graph learning, opcode models, noisy-OR fusion, selective
classification, EIP-7702 phishing, ERC-4337 triggering, and cross-chain measurement are prior
art and are cited as such.

Primary sources:

- Huang et al., USENIX Security 2026: https://www.usenix.org/conference/usenixsecurity26/presentation/huang-mingyuan
- Qi et al., arXiv:2512.12174: https://arxiv.org/abs/2512.12174
- Zhuang et al., IJCAI 2020: https://doi.org/10.24963/ijcai.2020/454
- COBRA, ASE 2024: https://arxiv.org/abs/2410.20712
- BugSweeper, AAAI 2026: https://doi.org/10.1609/aaai.v40i1.37021
- SelectiveNet, ICML 2019: https://proceedings.mlr.press/v97/geifman19a.html
