# Phase 3A Report — Excel-Based Human Review Preparation

Branch `tps-revision-v3`. This phase built a simplified, Excel-based, LLM-assisted
collaborative review workflow for contributors without prior EIP-7702 security experience —
explicitly **not** a blinded independent annotation process (that remains available, unused,
in the existing FastAPI `annotation_app`, which was left completely unchanged: still 230
seeded items, 400 assignments, **0 annotations**, verified below).

## Files created

**Guides and protocol**
- `revision_v3/human_eval/REVIEWER_GUIDE.md` — full educational background (EOA/EIP-7702/
  delegate/authorization concepts, worked example, ordered review checklist, 6 synthetic
  educational examples)
- `revision_v3/human_eval/LLM_REVIEW_METHOD.md` — exact instructions followed, model
  identifier (Claude Sonnet 5), generation date (2026-07-30), and why 17/20 items were scored
  UNCERTAIN by the LLM
- `revision_v3/human_eval/PILOT_REVIEW_INSTRUCTIONS.md` — 10-step workflow + exact commands
- `revision_v3/human_eval/taxonomy.py` — single source of truth for the 3 primary labels, 9
  UNSAFE / 8 UNCERTAIN / 5 SAFE reason categories, confidence levels, and forbidden-field list

**Evidence and LLM analysis**
- `revision_v3/experiments/excel_review/dump_pilot_evidence.py` +
  `revision_v3/human_eval/llm_reviews/pilot_evidence_dump.json` (20 evidence packets, reusing
  Phase 2's `packet_builder.py`)
- `revision_v3/human_eval/llm_reviews/pilot_llm_reviews.json` (20 real, individually-reasoned
  LLM preliminary analyses — not templated placeholders)

**Excel tooling and workbooks**
- `revision_v3/experiments/excel_review/excel_builder.py` — shared sheet/column/dropdown/
  protection builder, reused by every workbook
- `revision_v3/experiments/excel_review/build_pilot_workbook.py` → `Pilot_Review.xlsx`
- `revision_v3/human_eval/create_reviewer_copy.py`
- `revision_v3/experiments/excel_review/build_master_workbook.py` +
  `revision_v3/human_eval/import_reviewer_workbook.py` → `Pilot_Master_Adjudication.xlsx`
- `revision_v3/experiments/excel_review/summarize_pilot.py` →
  `revision_v3/reports/PILOT_REVIEW_SUMMARY.md` (currently `PENDING_REVIEWS`)

**Prepared, unrun Gold-Dev/Gold-Test tooling** (Part 11)
- `revision_v3/experiments/excel_review/dump_gold_evidence.py`
- `revision_v3/experiments/excel_review/build_gold_review_workbook.py`
- `revision_v3/experiments/excel_review/build_gold_master_workbook.py`

**Tests**
- `revision_v3/tests/test_phase3a_excel_review.py` (20 tests, all passing)

## Pilot workbook structure

`Pilot_Review.xlsx`: 5 sheets — `START_HERE`, `EIP7702_GUIDE`, `REVIEW_CHECKLIST`, `EXAMPLES`,
`PILOT_ITEMS`. The items sheet has 39 columns across 4 color-coded groups (18 blue evidence
columns, 7 yellow LLM columns, 9 green contributor columns, 5 orange lead-author-only columns),
frozen header row, autofilter, wrapped text, and 7 data-validation dropdowns (label, reason
category, confidence, agree-with-LLM, and their lead-author-only duplicates). Lead-author
columns are protection-locked (`ws.protection.sheet = True`); every other cell remains
editable — verified by `test_final_label_columns_remain_locked_in_reviewer_copy`.

`Pilot_Master_Adjudication.xlsx`: `MASTER_ITEMS` sheet (evidence + LLM columns +
`disagreement_summary` + `discussion_notes_combined` + lead-author columns) plus an
`_IMPORT_LOG` sheet. Contributor sections (4 columns each: `{Name}_label`, `{Name}_reason_category`,
`{Name}_confidence`, `{Name}_rationale`) are inserted dynamically by
`import_reviewer_workbook.py`, one per import — the workbook currently has **zero** contributor
sections (clean, unimported state), matching the stop condition.

## Evidence availability

Every evidence field is bytecode-derived (Phase 2's `packet_builder.py`, structurally
incapable of carrying model scores or source labels — enforced by `FORBIDDEN_FIELDS` and
tested in `test_workbook_contains_no_forbidden_fields` /
`test_workbook_cell_values_contain_no_forbidden_substrings`). Known limitations, explicitly
marked `NOT_AVAILABLE_OFFLINE` rather than guessed: no decompiler output (only a 60-opcode
disassembly prefix + full structural counts), no live verified-source check, no on-chain
authorization/transaction history. These same limitations directly shaped the LLM review
distribution (see below).

## LLM-review method summary

20 individually-reasoned preliminary analyses (not a templated classifier) — see
`LLM_REVIEW_METHOD.md` for the full instruction set. Distribution: **17 UNCERTAIN, 3 SAFE, 0
UNSAFE**. This is a calibrated consequence of the actual evidence depth available (a 60-opcode
prefix plus aggregate counts, not a full trace), not a generation failure — the guide's own
explicit instruction is "when evidence is insufficient, choose UNCERTAIN," and the LLM was
held to the same rule as human reviewers. Two items received an elevated-concern flag despite
an UNCERTAIN label (unguarded-looking `SELFDESTRUCT`; asset-transfer selectors with zero
backing storage state) and are called out by item ID in `llm_points_to_verify`. The 3 SAFE
proposals are each backed by a **named, positive** access-control signal (a complete
OpenZeppelin Ownable or Initializable+AccessControl selector set, or a recognized
self-call-only `ADDRESS==CALLER` guard pattern) — never merely an absence of red flags.

## Contributor workflow

10-step process documented in `PILOT_REVIEW_INSTRUCTIONS.md`: generate copy → contributor
reads guide/checklist/examples → reads LLM review → checks evidence → records independent
judgment → optional discussion → returns file → lead author imports → lead author reads
disagreements/discussion → lead author assigns `final_label`. Verified end-to-end in this
phase with synthetic test data (created, imported, validated, disagreement-tested, then fully
reset — no test data remains in any delivered file).

## Known evidence limitations (carried into the guide and every LLM review)

No decompiler, no live verified-source lookup, no on-chain authorization/transaction history —
all explicitly marked, never guessed at. Reviewers are told this directly in
`REVIEWER_GUIDE.md` §5 and see the same markers in the `verified_source_status` and
`authorization_history_summary` evidence columns.

## Two real bugs found and fixed during this phase

1. **CUBLAS-unrelated Excel bug**: `import_reviewer_workbook.py`'s disagreement-summary
   calculation initially matched any column ending in `_label`, which incorrectly counted
   `llm_proposed_label` (and, in a second pass, `final_label`) as if they were human
   contributor votes. Fixed by explicitly excluding both from the vote-counting columns;
   regression-tested in `test_disagreement_calc_excludes_llm_and_final_columns`.
2. An `openpyxl` deprecation warning (`Protection.copy()`) was cleaned up in `excel_builder.py`
   while verifying the test suite — cosmetic, not a correctness issue, but left no warnings in
   the final test run.

## Exact commands

**Generate a contributor copy:**
```bash
python3 revision_v3/human_eval/create_reviewer_copy.py \
  --input revision_v3/human_eval/Pilot_Review.xlsx \
  --reviewer "Contributor Name" \
  --output revision_v3/human_eval/reviewer_copies/Pilot_Review_Contributor_Name.xlsx
```

**Import a completed workbook:**
```bash
python3 revision_v3/human_eval/import_reviewer_workbook.py \
  --master revision_v3/human_eval/Pilot_Master_Adjudication.xlsx \
  --contributor-file revision_v3/human_eval/reviewer_copies/Pilot_Review_Contributor_Name.xlsx
```

**Generate the Pilot summary:**
```bash
python3 revision_v3/experiments/excel_review/summarize_pilot.py
```

**(Future, not run in this phase) Generate Gold-Dev/Gold-Test workbooks once explicitly instructed:**
```bash
python3 revision_v3/experiments/excel_review/dump_gold_evidence.py --sample-set gold_dev
python3 revision_v3/experiments/excel_review/build_gold_review_workbook.py --sample-set gold_dev
python3 revision_v3/experiments/excel_review/build_gold_master_workbook.py --sample-set gold_dev
# repeat with --sample-set gold_test
```

## Confirmation: zero human labels were fabricated

- `revision_v3/human_eval/Pilot_Master_Adjudication.xlsx`'s `_IMPORT_LOG` sheet is empty (no
  contributor has been imported).
- Every `final_label`, `final_reason_category`, `final_rationale`, and
  `final_decision_date` cell in both `Pilot_Review.xlsx` and `Pilot_Master_Adjudication.xlsx`
  is blank.
- `revision_v3/reports/PILOT_REVIEW_SUMMARY.md` reports `PENDING_REVIEWS`, not fabricated
  statistics.
- The existing FastAPI `annotation_app` database is unchanged from Phase 2's end state: 230
  items, 400 assignments, **0 annotations** (checked live, this phase, via `sqlite3`).
- `pilot_manifest.csv`, `gold_dev_manifest.csv`, `gold_test_manifest.csv`, and
  `gold_test_hashes.json` are byte-for-byte unchanged from before this phase began (MD5
  comparison against hashes recorded at the start of this session, tested in
  `test_phase3a_excel_review.py`).
- No `Gold_Dev_Review.xlsx`, `Gold_Test_Review.xlsx`, or their master-adjudication equivalents
  exist anywhere in the repository.
- Frozen-hash guard (`revision_v2/experiments/common/frozen.py verify`) reports `OK: 144
  frozen files verified unchanged` before and after this phase.
- Full test suite: **85/85 passing** (32 Phase 1 + 33 Phase 2 + 20 Phase 3A).

## Stop condition compliance

The annotation website was not started (not modified either — verified unchanged above).
Gold-Dev review was not started (no workbook exists). Gold-Test review was not started (no
workbook exists; the frozen sample and its hash manifest are byte-identical to before this
phase). No model was retrained. No ML performance was evaluated. No manuscript file was
touched.
