"""Check 4 — business rules.  (Day 1, Block 4)

Rules that are true regardless of who is asking: refund windows, order states,
amount ceilings. These are policy, not authorization, and they belong in code
for the same reason authorization does — a rule stated in a prompt is a
suggestion.

WORKSHOP 1, PHASE C — implement this.
"""

from __future__ import annotations

from typing import Any

from ..boundary import Decision, Session, ToolRequest


def business_rules(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    # TODO(Block 4): e.g. never refund more than the order total; never refund
    # an order already refunded; never cancel a delivered order.
    return Decision.allow("not_implemented")
