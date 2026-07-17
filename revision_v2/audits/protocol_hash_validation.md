# Protocol Hash Validation

Four of five entries in `revision_v2/protocols/protocols.sha256` verify. The donor-isolation
entry does not: the ledger records `7bc2cb3a...`, while the committed file hashes to
`73a7e798...`.

Git history identifies the cause. Commit `3a46bf348d20c18acad3dddc1b1c215b67f73801` amended
the donor protocol to v1.1, replacing hashed 60/20/20 donor assignment with fold-aligned
assignment, and records that the amendment occurred before any donor-isolated result was
generated. The hash ledger was not refreshed in that commit. The G-MUT/G-VOL/G-ADV v2 code
and results implement the committed v1.1 rule.

Finalization does not rewrite either frozen protocol artifact. This is disclosed as a stale
protocol-ledger entry and reproducibility deviation, separate from the 144-file frozen-evidence
guard, which continues to pass.
