"""Revision v3 annotation application: minimal FastAPI + SQLite + server-rendered HTML.
No React/Vue/Node build system -- Jinja2 templates only, forms POST directly.

Run with:  uvicorn app:app --app-dir revision_v3/annotation_app --port 8420

Reviewer identity is a simple typed-in reviewer_id (internal tool, no external auth
provider); a signed-nothing cookie just remembers the last-used reviewer_id for convenience.
This is NOT a security boundary -- the tool is intended for a small, trusted internal review
team, matching the "fastest defensible stack" recommendation from the Phase 1 audit.
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agreement import compute_agreement_stats  # noqa: E402
from annotation_validation import validate_annotation_submission  # noqa: E402
from assignment_rules import apply_post_submit_rules  # noqa: E402
from constants import CONFIDENCE_LEVELS, INDETERMINATE_REASONS, PRIMARY_LABELS, UNSAFE_CATEGORIES  # noqa: E402
from db import db_session, get_connection, init_db, log_action, now_iso  # noqa: E402
from review_gate import postcutoff_review_unlock_status  # noqa: E402

# Reviewer pools for dynamic second-review / adjudicator assignment (Gold-Dev / Gold-Test).
# Configurable via env vars; defaults assume a 3-person review team (R1, R2 primary; R3 also
# available as adjudicator/second-reviewer pool member).
SECOND_REVIEWER_POOL = os.environ.get("SECOND_REVIEWER_POOL", "R1,R2,R3").split(",")
ADJUDICATOR_POOL = os.environ.get("ADJUDICATOR_POOL", "R3").split(",")

HERE = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AuthGuard-7702 Revision v3 Annotation", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))


def _reviewer_id(request: Request) -> str | None:
    return request.cookies.get("reviewer_id")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    reviewer_id = _reviewer_id(request)
    if not reviewer_id:
        return RedirectResponse("/login")
    return RedirectResponse("/dashboard")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_submit(reviewer_id: str = Form(...)):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO reviewers (reviewer_id, display_name, role, created_at) VALUES (?, ?, 'primary', ?) "
            "ON CONFLICT(reviewer_id) DO NOTHING",
            (reviewer_id, reviewer_id, now_iso()),
        )
        log_action(conn, reviewer_id, "login")
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("reviewer_id", reviewer_id, max_age=60 * 60 * 24 * 30)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    reviewer_id = _reviewer_id(request)
    if not reviewer_id:
        return RedirectResponse("/login")
    conn = get_connection()
    my_assignments = conn.execute(
        "SELECT a.item_id, a.status, a.is_adjudication, i.sample_set FROM assignments a "
        "JOIN items i ON i.item_id = a.item_id WHERE a.reviewer_id = ? ORDER BY a.assigned_at",
        (reviewer_id,),
    ).fetchall()
    overall = conn.execute(
        "SELECT i.sample_set, COUNT(DISTINCT i.item_id) as n_items, "
        "SUM(CASE WHEN a.status='completed' THEN 1 ELSE 0 END) as n_completed_assignments, "
        "COUNT(a.assignment_id) as n_assignments "
        "FROM items i LEFT JOIN assignments a ON a.item_id = i.item_id GROUP BY i.sample_set"
    ).fetchall()
    conn.close()
    postcutoff_unlocked, postcutoff_gate_reason = postcutoff_review_unlock_status()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "reviewer_id": reviewer_id,
        "my_assignments": my_assignments, "overall": overall,
        "postcutoff_unlocked": postcutoff_unlocked,
        "postcutoff_gate_reason": postcutoff_gate_reason,
    })


@app.get("/review/next", response_class=HTMLResponse)
def review_next(request: Request):
    reviewer_id = _reviewer_id(request)
    if not reviewer_id:
        return RedirectResponse("/login")
    conn = get_connection()
    postcutoff_unlocked, _ = postcutoff_review_unlock_status()
    query = (
        "SELECT a.item_id FROM assignments a JOIN items i ON i.item_id=a.item_id "
        "WHERE a.reviewer_id = ? AND a.status != 'completed' "
    )
    if not postcutoff_unlocked:
        query += "AND i.sample_set != 'postcutoff' "
    row = conn.execute(query + "ORDER BY a.assigned_at LIMIT 1", (reviewer_id,)).fetchone()
    conn.close()
    if row is None:
        return templates.TemplateResponse("no_more_items.html", {"request": request, "reviewer_id": reviewer_id})
    return RedirectResponse(f"/review/{row['item_id']}")


@app.get("/review/{item_id}", response_class=HTMLResponse)
def review_item(request: Request, item_id: str):
    reviewer_id = _reviewer_id(request)
    if not reviewer_id:
        return RedirectResponse("/login")
    conn = get_connection()
    assignment = conn.execute(
        "SELECT * FROM assignments WHERE item_id = ? AND reviewer_id = ?", (item_id, reviewer_id),
    ).fetchone()
    if assignment is None:
        conn.close()
        return HTMLResponse("Item not assigned to this reviewer.", status_code=403)

    item = conn.execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()
    postcutoff_unlocked, gate_reason = postcutoff_review_unlock_status()
    if item["sample_set"] == "postcutoff" and not postcutoff_unlocked:
        conn.close()
        return HTMLResponse(
            "Post-cutoff review is locked: " + gate_reason, status_code=423
        )

    if assignment["status"] == "pending":
        conn.execute("UPDATE assignments SET status = 'in_progress' WHERE assignment_id = ?", (assignment["assignment_id"],))
        conn.commit()

    evidence = json.loads(item["evidence_json"])
    disassembly_preview = evidence.get("opcode_disassembly", [])[:120]

    existing = conn.execute(
        "SELECT * FROM annotations WHERE item_id = ? AND reviewer_id = ? AND is_adjudication = ?",
        (item_id, reviewer_id, int(bool(assignment["is_adjudication"]))),
    ).fetchone()

    adjudication_context = None
    if assignment["is_adjudication"]:
        prior = conn.execute(
            "SELECT reviewer_id, label, unsafe_category, indeterminate_reason, confidence, rationale "
            "FROM annotations WHERE item_id = ? AND is_adjudication = 0 AND is_draft = 0", (item_id,),
        ).fetchall()
        adjudication_context = [dict(r) for r in prior]

    log_action(conn, reviewer_id, "view_item", item_id)
    conn.commit()
    conn.close()

    return templates.TemplateResponse("review.html", {
        "request": request, "reviewer_id": reviewer_id, "item_id": item_id,
        "evidence": evidence, "disassembly_preview": disassembly_preview,
        "existing": existing, "is_adjudication": bool(assignment["is_adjudication"]),
        "adjudication_context": adjudication_context,
        "PRIMARY_LABELS": PRIMARY_LABELS, "UNSAFE_CATEGORIES": UNSAFE_CATEGORIES,
        "INDETERMINATE_REASONS": INDETERMINATE_REASONS, "CONFIDENCE_LEVELS": CONFIDENCE_LEVELS,
    })


@app.post("/review/{item_id}")
def review_submit(
    request: Request, item_id: str,
    label: str = Form(...), unsafe_category: str = Form(""), indeterminate_reason: str = Form(""),
    confidence: str = Form(...), rationale: str = Form(""), evidence_consulted: str = Form(""),
    action: str = Form("submit"),  # "save_draft" | "submit"
):
    reviewer_id = _reviewer_id(request)
    if not reviewer_id:
        return RedirectResponse("/login")
    with db_session() as conn:
        assignment = conn.execute(
            "SELECT * FROM assignments WHERE item_id = ? AND reviewer_id = ?", (item_id, reviewer_id),
        ).fetchone()
        if assignment is None:
            return HTMLResponse("Item not assigned to this reviewer.", status_code=403)
        item = conn.execute(
            "SELECT sample_set FROM items WHERE item_id = ?", (item_id,)
        ).fetchone()
        postcutoff_unlocked, gate_reason = postcutoff_review_unlock_status()
        if item["sample_set"] == "postcutoff" and not postcutoff_unlocked:
            return HTMLResponse(
                "Post-cutoff review is locked: " + gate_reason, status_code=423
            )
        existing_final = conn.execute(
            "SELECT annotation_id FROM annotations WHERE item_id = ? AND reviewer_id = ? "
            "AND is_adjudication = ? AND is_draft = 0",
            (item_id, reviewer_id, int(bool(assignment["is_adjudication"]))),
        ).fetchone()
        if existing_final is not None:
            return HTMLResponse(
                "This judgment is finalized and immutable. Record any correction through a "
                "documented amendment rather than overwriting it.",
                status_code=409,
            )
        try:
            validated = validate_annotation_submission(
                label=label,
                unsafe_category=unsafe_category,
                indeterminate_reason=indeterminate_reason,
                confidence=confidence,
                rationale=rationale,
                evidence_consulted=evidence_consulted,
                action=action,
            )
        except ValueError as error:
            return HTMLResponse(f"Invalid annotation: {error}", status_code=422)
        is_adjudication = int(bool(assignment["is_adjudication"]))
        is_draft = int(bool(validated["is_draft"]))

        conn.execute(
            "INSERT INTO annotations (item_id, reviewer_id, is_adjudication, label, unsafe_category, "
            "indeterminate_reason, confidence, rationale, evidence_consulted, is_draft, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(item_id, reviewer_id, is_adjudication) DO UPDATE SET "
            "label=excluded.label, unsafe_category=excluded.unsafe_category, "
            "indeterminate_reason=excluded.indeterminate_reason, confidence=excluded.confidence, "
            "rationale=excluded.rationale, evidence_consulted=excluded.evidence_consulted, "
            "is_draft=excluded.is_draft, updated_at=excluded.updated_at",
            (item_id, reviewer_id, is_adjudication, validated["label"],
             validated["unsafe_category"], validated["indeterminate_reason"],
             validated["confidence"], validated["rationale"],
             validated["evidence_consulted"],
             is_draft, now_iso(), now_iso()),
        )
        if not is_draft:
            conn.execute("UPDATE assignments SET status = 'completed' WHERE assignment_id = ?", (assignment["assignment_id"],))
        log_action(conn, reviewer_id, "save_draft" if is_draft else "submit_annotation", item_id,
                   {"label": validated["label"]})

        if not is_draft and not is_adjudication:
            item = conn.execute("SELECT sample_set FROM items WHERE item_id = ?", (item_id,)).fetchone()
            apply_post_submit_rules(conn, item_id, item["sample_set"], SECOND_REVIEWER_POOL, ADJUDICATOR_POOL)

    if is_draft:
        return RedirectResponse(f"/review/{item_id}", status_code=303)
    return RedirectResponse("/review/next", status_code=303)


@app.get("/admin/agreement", response_class=HTMLResponse)
def agreement_page(request: Request):
    stats = compute_agreement_stats()
    return templates.TemplateResponse("agreement.html", {"request": request, "stats": stats})


@app.get("/admin/agreement.json")
def agreement_json():
    return JSONResponse(compute_agreement_stats())


@app.get("/admin/audit_log.json")
def audit_log_json(limit: int = 200):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY log_id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return JSONResponse([dict(r) for r in rows])
