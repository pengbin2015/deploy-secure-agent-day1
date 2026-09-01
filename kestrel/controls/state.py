"""State and memory controls — surface 7.  (Day 2, Block 5)

The most consequential surface in the system, because a poisoned memory is a
breach that persists after the conversation that caused it has ended.

The rule from Day 1, applied to memory: the model may PROPOSE a memory. Code
and humans decide what sticks.

    preference   the user set it themselves          -> allowed
    procedural   how the agent does things           -> human approval
    policy       what the agent is ALLOWED to do     -> human approval

WORKSHOP 2 — implement this.
"""

from __future__ import annotations

import time
from typing import Any

from .. import db
from ..events import ALLOW, DENY, HOLD, LOG, SecurityEvent
from ..surfaces import Surface

KINDS = ("preference", "procedural", "policy")


def propose_note(session_id: str, kind: str, body: str, origin_surface: int,
                 *, turn_id: str | None = None,
                 scenario_id: str | None = None) -> bool:
    """The model proposes a memory. This function decides whether it sticks."""
    # TODO(Day 2, Block 5): allow 'preference' written by the user themselves;
    # hold 'procedural' and 'policy' for approval; refuse anything whose origin
    # surface is untrusted. Record origin_surface and trusted on the row —
    # the columns already exist, which is the point.
    decision, reason = ALLOW, "not_implemented"
    LOG.emit(
        SecurityEvent(
            surface=int(Surface.STATE_MEMORY),
            control="memory_write",
            decision=decision,
            reason=reason,
            session_id=session_id,
            scenario_id=scenario_id,
            turn_id=turn_id,
            detail={"kind": kind, "origin_surface": origin_surface},
        )
    )
    if decision != ALLOW:
        return False
    db.execute(
        "INSERT INTO notes (session_id, kind, body, origin_surface, trusted, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (session_id, kind, body, origin_surface, 0, time.time()),
    )
    return True


def recall(session_id: str, *, trusted_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT kind, body, origin_surface, trusted FROM notes WHERE session_id = ?"
    if trusted_only:
        sql += " AND trusted = 1"
    return db.query(sql, (session_id,))
