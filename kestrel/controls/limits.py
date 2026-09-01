"""Check 6 — rate and action limits.  (Day 2, Block 10)

The last line. When everything above has been satisfied and the action is
still wrong, limits decide how much damage one session can do before someone
notices. The goal is not prevention; it is that the worst case is a bill you
survive and an alert you can act on.

WORKSHOP 2 — implement this.
"""

from __future__ import annotations

from typing import Any

from ..boundary import Decision, Session, ToolRequest


def apply_limits(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    # TODO(Day 2, Block 10): cap tool calls per turn (CONFIG.max_tool_calls_per_turn)
    # and refund value per session (CONFIG.max_refund_cents_per_session).
    # Deny with reason "rate_limited" or "value_limit_exceeded".
    return Decision.allow("not_implemented")
