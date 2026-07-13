# Frozen Family Structure (Task A)

Global clustering of all **3258** contracts (leakage-safe, cross-class families kept together). Deterministic MinHash (blake2b, 128 perms) over opcode 4-grams; union-find at threshold. Frozen `family_id` = threshold **0.85**.

| threshold | families | singletons | singleton % | largest family | cross-chain fams | cross-chain % | cross-class fams | cross-class % |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.75 | 1120 | 749 | 66.9 | 89 | 160 | 14.3 | 49 | 4.4 |
| 0.85 (**frozen**) | 1329 | 912 | 68.6 | 58 | 184 | 13.8 | 44 | 3.3 |
| 0.9 | 1511 | 1083 | 71.7 | 48 | 196 | 13.0 | 36 | 2.4 |

## Per-class family counts at frozen threshold 0.85

A family is counted for a class if >=1 member has that class. Cross-class families (below) are the contamination signal.

| class | rows | distinct families containing this class |
|---|---:|---:|
| malicious | 793 | 214 |
| benign_cleared | 1657 | 711 |
| benign_general | 800 | 440 |
| benign_AA | 8 | 8 |

## Malicious population (family/singleton characterization, Claim 2)

- Malicious contracts: **793**
- Distinct families containing malicious: **214**
- Purely-malicious families: **178**
- Malicious singletons (family size 1 counting malicious members only): **113** (52.8% of malicious families)
- Largest malicious family size: **58**

Top-10 malicious families by size:

| family_id | malicious members |
|---|---:|
| F00004 | 58 |
| F00008 | 48 |
| F00023 | 35 |
| F00031 | 34 |
| F00006 | 32 |
| F00013 | 26 |
| F00020 | 19 |
| F00007 | 19 |
| F00001 | 18 |
| F00038 | 13 |
