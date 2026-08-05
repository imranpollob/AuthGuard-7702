# Pilot Review — Workflow Instructions (Lead Author Reference)

This is an **LLM-assisted collaborative consensus process**, not blinded independent
annotation. Contributors see the AI assistant's preliminary analysis, may discuss difficult
cases with each other, and the lead author makes the final call after reading everything. This
document is the step-by-step operational guide for running it.

## Workflow

1. **Lead author sends one contributor-specific Excel copy to each contributor**, generated
   with `create_reviewer_copy.py` (one invocation per contributor — see exact commands below).
2. **Contributor reads the guide and checklist** (`EIP7702_GUIDE` and `REVIEW_CHECKLIST`
   sheets in their copy).
3. **Contributor reads the LLM first review** for each item (yellow columns in `PILOT_ITEMS`).
4. **Contributor checks the evidence** (blue columns) — the LLM review is a starting point to
   verify or challenge, not an answer to copy.
5. **Contributor records a label, reason, confidence, and rationale** (green columns) for every
   item.
6. **Contributors may discuss difficult cases** — informally (chat, call, etc.) or by writing
   in the `questions_or_discussion_notes` column. There is no built-in chat feature in the
   workbook; discussion happens outside it, and conclusions/open questions should be recorded
   in that column for the lead author to see.
7. **Contributors return their completed Excel files** to the lead author (email, shared drive,
   etc. — outside the scope of this tooling).
8. **Lead author imports all reviews into the master workbook** with
   `import_reviewer_workbook.py`, one invocation per returned file.
9. **Lead author reviews disagreements and discussion notes** — the master workbook's
   `disagreement_summary` column flags every item where imported contributors did not agree
   unanimously; `discussion_notes_combined` aggregates every contributor's notes for that item.
10. **Lead author assigns the final reference label** by filling in `final_label`,
    `final_reason_category`, `final_rationale`, and `final_decision_date` directly in
    `Pilot_Master_Adjudication.xlsx`'s `MASTER_ITEMS` sheet.

**Contributors are not required to understand the ML model.** They only need to decide
whether the delegate appears SAFE, UNSAFE, or UNCERTAIN based on the provided security
evidence (and the guide, checklist, and examples supplied).

## Exact commands

### 1. Generate a contributor copy

```bash
python3 revision_v3/human_eval/create_reviewer_copy.py \
  --input revision_v3/human_eval/Pilot_Review.xlsx \
  --reviewer "Jane Doe" \
  --output revision_v3/human_eval/reviewer_copies/Pilot_Review_Jane_Doe.xlsx
```

Repeat once per contributor, changing `--reviewer` and `--output`.

### 2. Import a completed contributor file

```bash
python3 revision_v3/human_eval/import_reviewer_workbook.py \
  --master revision_v3/human_eval/Pilot_Master_Adjudication.xlsx \
  --contributor-file revision_v3/human_eval/reviewer_copies/Pilot_Review_Jane_Doe.xlsx
```

The importer will **reject** (nonzero exit code, no partial write) if: item IDs don't match the
master exactly, any label is not one of SAFE/UNSAFE/UNCERTAIN, any reason category doesn't
belong to the label it's paired with, or this reviewer name was already imported. It will
**warn but still import** if some items have no `contributor_label` filled in (reported by
item ID so you can follow up).

### 3. Assign final labels

Open `revision_v3/human_eval/Pilot_Master_Adjudication.xlsx`, go to `MASTER_ITEMS`, read the
evidence + LLM review + every imported contributor's section + `disagreement_summary` +
`discussion_notes_combined` for each item, and fill in the four `final_*` columns yourself.
**No tool in this package will do this step for you or suggest a majority-vote answer** — that
is intentional (per the audit brief: "the lead author will manually determine the final label
after reading all reviews and discussion notes").

### 4. Generate the summary report

```bash
python3 revision_v3/experiments/excel_review/summarize_pilot.py
```

Reads `Pilot_Master_Adjudication.xlsx` and writes
`revision_v3/reports/PILOT_REVIEW_SUMMARY.md`. Safe to run at any point — with zero
contributors imported it reports `PENDING_REVIEWS`; with some final labels still blank it
reports partial statistics and calls out which items are still open.

## What this workflow deliberately does NOT do

- It does not compute or suggest a majority-vote final label anywhere.
- It does not compute or report ML accuracy at any point during the Pilot.
- It does not blind contributors from each other's identity or from the LLM's opinion — this
  is a collaborative, not an independent-blinded, process (see
  `revision_v3/reports/PHASE3A_EXCEL_REVIEW_PREPARATION.md` for why the existing blinded
  FastAPI annotation app was not used for this workflow).
