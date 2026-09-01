"""Conversation state and long-term memory.  (Day 2, Block 5)

A SQLite checkpointer, deliberately small. If LangGraph is installed the graph
uses its SqliteSaver instead; the security properties are identical, because
they live in what may be written rather than in where it is stored.
"""

from __future__ import annotations

import json
import time
from typing import Any

from .. import db


def save_checkpoint(thread_id: str, state: dict[str, Any]) -> int:
    row = db.query(
        "SELECT COALESCE(MAX(seq), 0) AS s FROM turn_log WHERE thread_id = ?",
        (thread_id,),
    )
    seq = int(row[0]["s"]) + 1
    db.execute(
        "INSERT INTO turn_log (thread_id, seq, blob, created_at) VALUES (?,?,?,?)",
        (thread_id, seq, json.dumps(state, default=str), time.time()),
    )
    return seq


def load_checkpoint(thread_id: str) -> dict[str, Any] | None:
    rows = db.query(
        "SELECT blob FROM turn_log WHERE thread_id = ? ORDER BY seq DESC LIMIT 1",
        (thread_id,),
    )
    return json.loads(rows[0]["blob"]) if rows else None


def history(thread_id: str) -> list[dict[str, Any]]:
    return db.query(
        "SELECT seq, blob, created_at FROM turn_log WHERE thread_id = ? ORDER BY seq",
        (thread_id,),
    )
