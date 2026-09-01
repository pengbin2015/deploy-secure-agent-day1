"""Checks 2 and 3 — authorize against session identity, then scope the
resource to the caller.  (Day 1, Block 4)

These are two different questions and they fail differently:

    authorize_identity  may this caller use this verb at all?
    scope_resources     does this particular row belong to this caller?

This morning's breach passed the first and never asked the second. The agent
knew who was talking; nobody checked whose order it was.

Authorization is decided against the authenticated session, never against
anything the model believes or the user claims.

WORKSHOP 1, PHASE C — implement both.
"""

from __future__ import annotations

from typing import Any

from ..boundary import Decision, Session, ToolRequest


#: Which roles may invoke which tools. Start here; the shape is the easy part.
TOOL_ROLES: dict[str, tuple[str, ...]] = {
    # "refund_order": ("customer", "agent"),
    # "change_email": ("agent",),
}


def authorize_identity(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    # TODO(Block 4): check session.roles against the verb being requested.
    # Deny with reason "role_not_permitted" when the caller may not use it.
    return Decision.allow("not_implemented")


def scope_resources(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    # TODO(Block 4): this is the fix for the anchor breach.
    #
    # For any argument that names a resource — order_id, customer_id — load the
    # row and confirm it belongs to session.customer_id. Deny with reason
    # "resource_not_owned_by_session".
    #
    # Do it here, at action time, against the session. Not in the prompt, not
    # in the tool, and not at the start of the conversation.
    return Decision.allow("not_implemented")
