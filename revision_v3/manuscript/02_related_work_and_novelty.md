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

De Rosa et al., *PhishingHook* (DSN 2025), compare 16 histogram, vision, language, and
vulnerability-model techniques for generic phishing-contract classification directly from EVM
bytecode. It rules out any claim that AuthGuard-7702 is the first pre-interaction bytecode phishing
classifier or the first comparison of opcode model families. Its labels and population differ from
authorization-specific delegate review, so published cross-dataset accuracy is not a fair
baseline. We instead retrain representative histogram+n-gram and learned sequence models using the
same labels, family holds, thresholds, seeds, and untouched population as DCRG.

Contract graphs, CFG/data-flow representations, and learned graph models are established prior
art, including Zhuang et al. (IJCAI 2020), SCGformer (IET Blockchain 2023), COBRA (ASE 2024),
and BugSweeper (AAAI 2026). Opcode-sequence learning and multi-view fusion are likewise not new.
The proposed DCRG claim is consequently narrower: an authority-relative, EIP-7702 execution
representation that types guards by what they authorize, connects them to reachable sensitive
capabilities, and records analysis gaps. A capability-only CFG, untyped guards, the Huang et al.
hook rule, sequence models, and full DCRG are required ablations/baselines.

## Selective prediction

Classification with a reject option and risk-coverage analysis are established, for example in
SelectiveNet (ICML 2019) and subsequent one-sided selective-classification work. We do not claim a
new selective-learning algorithm. The attempted low-risk tier failed on development labels and was
removed. The retained application contract emits `WARN`, `NO_MODEL_WARNING`, or `DEFER`;
incomplete semantic coverage and seed instability can defer, and `NO_MODEL_WARNING` is never a
safety or legitimacy judgment. Its value must be evaluated through warning/deferral behavior,
calibration, coverage, error audits, and legitimate-project controls—not by renaming classifier
uncertainty.

## Defensible novelty statement

Subject to independent-label validation, the paper's method novelty is a coverage-audited,
guard-aware representation for EIP-7702 delegate execution at the pre-authorization decision. The
benchmark contribution is a provenance-audited evaluation of that question, not a claim to the
first EIP-7702 attack dataset. Authority/protocol-actor superiority is not currently supported and
is not required for the primary claim. Generic CFG construction, graph learning, opcode models,
noisy-OR fusion, selective classification, EIP-7702 phishing, ERC-4337 triggering, and cross-chain
measurement are prior art and are cited as such.

Primary sources:

- Huang et al., USENIX Security 2026: https://www.usenix.org/conference/usenixsecurity26/presentation/huang-mingyuan
- Qi et al., arXiv:2512.12174: https://arxiv.org/abs/2512.12174
- De Rosa et al., PhishingHook, DSN 2025: https://doi.org/10.1109/DSN64029.2025.00033
- Zhuang et al., IJCAI 2020: https://doi.org/10.24963/ijcai.2020/454
- COBRA, ASE 2024: https://arxiv.org/abs/2410.20712
- BugSweeper, AAAI 2026: https://doi.org/10.1609/aaai.v40i1.37021
- SelectiveNet, ICML 2019: https://proceedings.mlr.press/v97/geifman19a.html
