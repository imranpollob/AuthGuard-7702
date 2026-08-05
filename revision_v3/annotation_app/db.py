"""SQLite schema and connection helpers for the Revision v3 annotation app.

Single-file SQLite database (revision_v3/annotation_app/annotation.db by default), stdlib
sqlite3 only -- no ORM, no external DB server, per the "minimal FastAPI + SQLite" mandate.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "ANNOTATION_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "annotation.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviewers (
    reviewer_id TEXT PRIMARY KEY,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'primary',  -- 'primary' | 'adjudicator' | 'admin'
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,          -- anon_id from the evidence packet
    sample_set TEXT NOT NULL,          -- 'pilot' | 'gold_dev' | 'gold_test' | 'postcutoff'
    evidence_json TEXT NOT NULL,       -- full evidence packet, JSON-serialized
    family_id TEXT,                     -- retained for isolation checks, never shown to reviewers
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    reviewer_id TEXT NOT NULL REFERENCES reviewers(reviewer_id),
    is_adjudication INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'in_progress' | 'completed'
    assigned_at TEXT NOT NULL,
    UNIQUE(item_id, reviewer_id, is_adjudication)
);

CREATE TABLE IF NOT EXISTS annotations (
    annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    reviewer_id TEXT NOT NULL REFERENCES reviewers(reviewer_id),
    is_adjudication INTEGER NOT NULL DEFAULT 0,
    label TEXT,                    -- NO_CONCRETE_UNSAFE_BEHAVIOR_FOUND | UNSAFE | INDETERMINATE | NOT_BYTECODE_SCREENABLE
    unsafe_category TEXT,          -- required iff label == UNSAFE
    indeterminate_reason TEXT,     -- required iff label in (INDETERMINATE, NOT_BYTECODE_SCREENABLE)
    confidence TEXT,               -- 'high' | 'medium' | 'low'
    rationale TEXT,
    evidence_consulted TEXT,       -- JSON list of evidence-field names the reviewer cites
    is_draft INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(item_id, reviewer_id, is_adjudication)
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    item_id TEXT,
    detail TEXT,
    timestamp TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_action(conn: sqlite3.Connection, actor: str, action: str, item_id: str | None = None, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, item_id, detail, timestamp) VALUES (?, ?, ?, ?, ?)",
        (actor, action, item_id, json.dumps(detail or {}), now_iso()),
    )
