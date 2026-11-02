"""SQLite log of RAG requests.

Governance rule: never store the original question. Store only safe_question,
and store no question text at all when the decision is "block".
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
DB_PATH = LOG_DIR / "usage.db"

_CREATE_EVENTS = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user TEXT,
    decision TEXT,
    reasons TEXT,
    safe_question TEXT,
    sources_used TEXT,
    warnings TEXT,
    answer_chars INTEGER,
    latency_ms INTEGER,
    error TEXT
)
"""


def log_event(
    *,
    user,
    decision,
    reasons,
    safe_question,
    sources_used,
    warnings,
    answer_chars,
    latency_ms,
    error=None,
):
    """Insert one request. A blocked question is stored with an empty safe_question."""
    if decision == "block":
        safe_question = ""

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO events (
                timestamp, user, decision, reasons, safe_question,
                sources_used, warnings, answer_chars, latency_ms, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                user,
                decision,
                json.dumps(reasons),
                safe_question,
                json.dumps(sources_used),
                json.dumps(warnings),
                answer_chars,
                latency_ms,
                error,
            ),
        )


def get_events():
    """Return every logged event, oldest first, for a later dashboard."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY id").fetchall()

    events = []
    for row in rows:
        event = dict(row)
        for key in ("reasons", "sources_used", "warnings"):
            event[key] = json.loads(event[key]) if event[key] else []
        events.append(event)
    return events


def _connect():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_EVENTS)
    return conn
