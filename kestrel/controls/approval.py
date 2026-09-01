"""Check 5 — require approval.  (Day 2, Block 9)

Some actions are irreversible enough that no amount of validation makes them
safe to take autonomously. Those get a human, and the human is asked *before*
the action, not shown a summary afterwards.

The list of what needs approval is the output of the Day 1 "who may say yes"
activity. Teams bring their own answers to this.

WORKSHOP 2 — implement this.
"""

from __future__ import annotations

from typing import Any

from ..boundary import Decision, Session, ToolRequest

#: Actions that stop and wait for a person. Decision.hold, not Decision.deny:
#: the request is not wrong, it is not yours alone to make.
NEEDS_APPROVAL: dict[str, Any] = {
    # "change_email": lambda req: True,
    # "refund_order": lambda req: req.args.get("amount_cents", 0) > 5000,
}


def require_approval(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    # TODO(Day 2, Block 9): return Decision.hold("approval_required") for the
    # actions your team decided a human must authorise.
    return Decision.allow("not_implemented")
