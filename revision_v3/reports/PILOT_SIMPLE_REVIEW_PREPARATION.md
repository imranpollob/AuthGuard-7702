# Pilot Simple Review — Preparation Report

Branch `tps-revision-v3`. This is a **simplification** of the Phase 3A Pilot review process,
not a replacement of it. Phase 3A's files (`Pilot_Review.xlsx`, `Pilot_Master_Adjudication.xlsx`,
`create_reviewer_copy.py`, `import_reviewer_workbook.py`, `REVIEWER_GUIDE.md`,
`PILOT_REVIEW_INSTRUCTIONS.md`, and their supporting scripts) were **not modified** and are
kept as archived supporting infrastructure. They are unused by this new workflow.

## What was created

- `revision_v3/human_eval/llm_reviews/pilot_plain_english_reviews.json` — a plain-English
  companion to Phase 3A's `pilot_llm_reviews.json`. Same 20 Pilot items, same underlying
  evidence and same conclusions (label/confidence come directly from the existing technical
  review — nothing was re-derived or re-analyzed) — restated without EVM/opcode jargon.
- `revision_v3/experiments/excel_review/build_simple_pilot_workbook.py` — builds the workbook.
  Reuses Phase 3A's `excel_builder.load_manifest_rows` / `load_packets_by_item_id` (unmodified
  imports, read-only) against the same frozen `pilot_manifest.csv` and
  `pilot_evidence_dump.json`.
- `revision_v3/human_eval/Pilot_Simple_Review.xlsx` — **the only file to be sent to
  contributors** for this Pilot round.

No reviewer-copy generator, no import workflow, no database, and no additional review package
were created for this workflow — contributors, the group discussion, and the lead author all
work directly in this single file, exactly as instructed.

## Workbook structure (verified)

3 sheets: `READ_ME`, `REVIEW_ITEMS`, `TECHNICAL_DETAILS`.

**READ_ME** — one page, five sections (what EIP-7702 is and why it matters, the four review
questions, the three label definitions, the step-by-step workflow, the calibration-meeting
recommendation), readable in about five minutes.

**REVIEW_ITEMS** — 20 data rows, 28 columns:
- 14 evidence columns (`item_id` … `missing_information`) — plain-English only, no bytecode,
  no opcode names, no selector lists
- 4 AI columns (`ai_proposed_label`, `ai_confidence`, `ai_explanation`, `ai_points_to_check`)
- 6 contributor columns (`contributor_1/2/3_label`, `contributor_1/2/3_reason`)
- 2 group columns (`group_discussion_note`, `agreed_group_label`)
- 2 lead-author columns (`final_label`, `final_reason`) — fill-shaded orange, protection-locked
  (`ws.protection.sheet == True`; contributor cells remain unlocked)

5 dropdowns (`contributor_1_label`, `contributor_2_label`, `contributor_3_label`,
`agreed_group_label`, `final_label`), each restricted to `SAFE` / `UNSAFE` / `UNCERTAIN` — the
same `PRIMARY_LABELS` from `revision_v3/human_eval/taxonomy.py` (no new taxonomy module was
needed; the existing 3-label set already matched this request exactly). Rationale fields stay
free text, as required. Frozen header row, autofilter, wrapped text, alternating row shading,
and per-column widths tuned for the long-text columns are all in place.

**TECHNICAL_DETAILS** — clearly banner-marked `OPTIONAL TECHNICAL REFERENCE` in red on a
warning-yellow highlight. 10 columns (`item_id`, `runtime_bytecode_hash`, `runtime_size`,
`selector_summary`, `opcode_summary`, `proxy_detection_details`, `source_code_link`,
`decompiler_output_path`, `documentation_link`, `evidence_limitations`), all derived
programmatically from the same evidence packets used in `REVIEW_ITEMS` — nothing here was
hand-written.

## Evidence availability

Same underlying evidence as Phase 3A: bytecode-derived structural counts and a 60-opcode
disassembly prefix, no decompiler, no live verified-source check, no on-chain authorization
history. `TECHNICAL_DETAILS.evidence_limitations` states this plainly for every item; the
`REVIEW_ITEMS.missing_information` column states the specific gap per item in plain language.

## AI-review method

The AI (Claude Sonnet 5) analysis in `pilot_plain_english_reviews.json` is a plain-English
restatement of Phase 3A's already-produced, evidence-grounded technical review
(`pilot_llm_reviews.json`) — the label, confidence, and underlying evidence are unchanged; only
the phrasing was simplified for readers with no EVM/smart-contract background. This keeps the
new workbook's AI analysis consistent with the documented Phase 3A methodology
(`LLM_REVIEW_METHOD.md`) rather than introducing a second, independent AI pass over the same
20 items. Distribution (unchanged from Phase 3A): 17 UNCERTAIN, 3 SAFE, 0 UNSAFE — a calibrated
consequence of limited evidence depth, not a generation failure. No AuthGuard score, AuthGuard
prediction, source-analyzer label, source positive/unflagged status, or FP/FN status was used
in producing these summaries, and none appears anywhere in the workbook (verified below). No
label was proposed as UNSAFE solely because CALL/DELEGATECALL/fallback/token-selectors/
unverified-source were present, and none was proposed as SAFE solely because a contract
belonged to a known project (in fact, `known_project` is null for all 20 Pilot items — the 3
SAFE proposals are each backed by a named, positive access-control signal instead: a complete
OpenZeppelin Ownable triad, a complete Initializable+AccessControl selector set, or a
recognized self-call-only `ADDRESS==CALLER` guard).

## Contributor workflow (documented in the READ_ME sheet)

1. Read READ_ME (~5 min).
2. Read the AI explanation for an item.
3. Check the plain-English evidence summary.
4. Open the source/explorer link only if needed.
5. Select SAFE / UNSAFE / UNCERTAIN.
6. Write 1–2 sentences explaining the decision.
7. Discuss difficult cases with other contributors.
8. Record the group's conclusion.
9. Lead author records `final_label` / `final_reason`.

Recommended first session: review the first 5 items together, walk through one SAFE, one
UNSAFE, and one UNCERTAIN worked example (from Phase 3A's `REVIEWER_GUIDE.md` /
`Pilot_Review.xlsx` EXAMPLES sheet, still available as reference), then discuss those 5 real
items as a group. The remaining 15 may be done individually or collaboratively afterward.

## Final verification (all checked programmatically)

- `REVIEW_ITEMS` has exactly 20 data rows, matching `pilot_manifest.csv`'s 20 `item_id` values
  exactly (set-equality check passed).
- `pilot_manifest.csv`, `gold_dev_manifest.csv`, `gold_test_manifest.csv`, and
  `gold_test_hashes.json` MD5 hashes are unchanged from the Phase 3A baseline — no resampling.
- No forbidden substring (`authguard_score`, `authguard_prediction`, `source_label`,
  `source_positive`, `source_unflagged`, `is_false_positive`, `is_false_negative`,
  `calibrated_score`, `raw_score`, `model_score`, `ref_model_mean`) appears anywhere in
  `REVIEW_ITEMS`.
- No raw bytecode (no cell starting with `0x60...`) appears in `REVIEW_ITEMS`.
- 5 dropdowns present, all restricted to exactly `SAFE,UNSAFE,UNCERTAIN`.
- All contributor, group, and lead-author columns are blank (0 non-blank cells) — zero human
  labels were fabricated.
- `final_label` cells are protection-locked; `contributor_1_label` cells are not — verified
  directly via each cell's `Protection.locked` value.
- No `Gold_Dev_Review.xlsx`, `Gold_Test_Review.xlsx`, or equivalent master-adjudication files
  exist anywhere in the repository.
- `revision_v2/experiments/common/frozen.py verify` reports `OK: 144 frozen files verified
  unchanged`.

## Exact command

```bash
python3 revision_v3/experiments/excel_review/build_simple_pilot_workbook.py
```

Regenerates `revision_v3/human_eval/Pilot_Simple_Review.xlsx` deterministically from the
frozen manifest, the frozen evidence dump, and the two (unmodified vs. this phase) review-text
JSON files. No other command is needed for this workflow — there is no reviewer-copy step and
no import step.

## Stop condition compliance

No human review was started (all contributor/group/final columns are blank). No Gold-Dev or
Gold-Test workbook was created. No model was retrained. No model performance was evaluated. No
manuscript file was touched. Phase 3A's existing files were not modified.
