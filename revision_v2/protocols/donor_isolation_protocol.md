# Donor Isolation Protocol (frozen before any donor-isolated result is read)

Seed: 7702. Replaces the v1 single-fixed-donor design
(`04_mutations._load_deadcode_source`: first `benign_general` row, shared across all
partitions) for every v2 flooded variant (F25/F50/F100/F200, M2 dead-code component, and the
compound M3+F200 condition).

## Donor corpus

- Primary donor corpus: task-aligned `benign_general` (797 rows), i.e. the corrected v1
  corpus, NOT the original CSV row (which the v1 code read even when quarantined).
- Sensitivity arm: donors drawn from `benign_cleared` (in-population weak negatives).
- Donor unit = executable region (pre-CBOR-metadata bytes) of a donor contract with
  ≥ 64 executable bytes (excludes designator-like and near-empty rows).

## Partition-isolated pools

For each outer fold `f`, each row of the evaluated population has a partition role:
train / validation / test (G-ADV) or train / test (G-MUT/G-VOL flooding of held-out rows).
Donor pools are built per fold from **donor families**, assigned by deterministic hash order:

1. Group eligible donors by frozen `family_id`.
2. Sort families by blake2b(family_id, salt=7702); split 60% train-pool / 20% val-pool /
   20% test-pool. A donor family belongs to exactly one role per fold (roles rotate with the
   fold index so all donors are exercised across folds).
3. Assertions per generated variant:
   - donor family's pool role == recipient partition role;
   - donor exact-bytecode hash appears in no other role's pool for that fold;
   - donor family != recipient family;
   - donor selection is a deterministic function of (fold, domain, recipient sid, condition,
     fraction) ONLY — never of the recipient label; positives and negatives share the policy.
4. Multi-donor: each variant samples its donor uniformly (seeded) from the role pool;
   role pools must contain ≥ 10 donor families (assert).

## Provenance ledger (one row per flooded variant)

`experiment_id, outer_fold, recipient_sid, recipient_address, recipient_family,
recipient_partition, recipient_label, donor_sid, donor_address, donor_family,
donor_partition_pool, donor_subset(benign_general|benign_cleared), condition,
flooding_fraction, byte_offset, byte_length, copied_segment_sha256, transformation_seed,
rng_domain`

Ledger completeness is asserted (every flooded variant has exactly one row) and the ledger is
hashed into the run manifest.

## Non-flooding mutations

M1 (metadata) and M2a (PUSH20) and M3 (selector rewrite) involve no donor; unchanged from v1
implementations (imported read-only).

## Status of v1 results

All v1 augmented-model G-ADV results remain frozen and are labeled **donor-confounded** in
internal reports; they are superseded by, never silently replaced with, v2 results.
