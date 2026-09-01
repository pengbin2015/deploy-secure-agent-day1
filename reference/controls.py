"""Reference implementations of the six ActionBoundary checks.

Facilitators run against these to show the same attack failing:

    KESTREL_CONTROLS=reference python -m kestrel attack cross_tenant_order_leak

Teams work against ``kestrel/controls/``. If you are handing the repo out and
would rather not ship the answers, delete this directory — nothing in the
student path imports it. ``make strip-reference`` does that for you.
"""

from __future__ import annotations

from typing import Any

from kestrel import db
from kestrel.boundary import Decision, Session, ToolRequest
from kestrel.config import CONFIG
from kestrel.tools.registry import ValidationError

# --------------------------------------------------------------------------
# 1. validate tool arguments
# --------------------------------------------------------------------------

def validate_arguments(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    registry = ctx["registry"]
    try:
        spec = registry.get(request.tool)
    except Exception:
        return Decision.deny("unknown_tool", tool=request.tool)

    # A wide tool cannot be made safe by validating it. Say so out loud rather
    # than pretending the schema check did something.
    if spec.wide:
        return Decision.deny(
            "tool_is_unconstrainable",
            tool=spec.name,
            note="free-form parameter; narrow the tool instead of guarding it",
        )
    try:
        clean = spec.validate(request.args)
    except ValidationError as exc:
        return Decision.deny("schema_violation", error=str(exc))
    return Decision.allow("schema_ok", args=clean)


# --------------------------------------------------------------------------
# 2. authorize against session identity
# --------------------------------------------------------------------------

TOOL_ROLES: dict[str, tuple[str, ...]] = {
    "get_order": ("customer", "agent", "supervisor"),
    "get_order_note": ("customer", "agent", "supervisor"),
    "list_my_orders": ("customer", "agent", "supervisor"),
    "refund_order": ("agent", "supervisor"),
    "cancel_order": ("customer", "agent", "supervisor"),
    "change_email": ("supervisor",),
    "apply_discount": ("agent", "supervisor"),
}


def authorize_identity(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    allowed = TOOL_ROLES.get(request.tool)
    if allowed is None:
        return Decision.deny("tool_not_in_policy", tool=request.tool)
    if not any(session.has_role(r) for r in allowed):
        return Decision.deny(
            "role_not_permitted",
            tool=request.tool,
            roles=list(session.roles),
            required=list(allowed),
        )
    return Decision.allow("role_ok")


# --------------------------------------------------------------------------
# 3. scope resources to the caller  <- the fix for the anchor breach
# --------------------------------------------------------------------------

def _order_owner(order_id: int) -> int | None:
    rows = db.query("SELECT customer_id FROM orders WHERE id = ?", (order_id,))
    return rows[0]["customer_id"] if rows else None


def scope_resources(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    args = request.args

    if "order_id" in args:
        owner = _order_owner(int(args["order_id"]))
        if owner is None:
            return Decision.deny("resource_not_found", order_id=args["order_id"])
        if owner != session.customer_id and not session.has_role("supervisor"):
            return Decision.deny(
                "resource_not_owned_by_session",
                order_id=args["order_id"],
                owner=owner,
                session_customer=session.customer_id,
            )

    if "customer_id" in args:
        if int(args["customer_id"]) != session.customer_id and not session.has_role(
            "supervisor"
        ):
            return Decision.deny(
                "resource_not_owned_by_session",
                customer_id=args["customer_id"],
                session_customer=session.customer_id,
            )

    return Decision.allow("scope_ok")


# --------------------------------------------------------------------------
# 4. business rules
# --------------------------------------------------------------------------

def business_rules(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    args = request.args

    if request.tool == "refund_order":
        rows = db.query(
            "SELECT total_cents, status FROM orders WHERE id = ?", (args["order_id"],)
        )
        if not rows:
            return Decision.deny("resource_not_found")
        order = rows[0]
        if int(args["amount_cents"]) > int(order["total_cents"]):
            return Decision.deny(
                "refund_exceeds_order_total",
                requested=args["amount_cents"],
                total=order["total_cents"],
            )
        already = db.query(
            "SELECT COALESCE(SUM(amount_cents),0) AS paid FROM refunds WHERE order_id = ?",
            (args["order_id"],),
        )[0]["paid"]
        if already + int(args["amount_cents"]) > int(order["total_cents"]):
            return Decision.deny("order_already_refunded", already_refunded=already)

    if request.tool == "apply_discount":
        if int(args.get("percent", 0)) > 20:
            return Decision.deny("discount_exceeds_policy_ceiling",
                                 percent=args["percent"], ceiling=20)

    if request.tool == "cancel_order":
        rows = db.query("SELECT status FROM orders WHERE id = ?", (args["order_id"],))
        if rows and rows[0]["status"] == "delivered":
            return Decision.deny("cannot_cancel_delivered_order")

    return Decision.allow("policy_ok")


# --------------------------------------------------------------------------
# 5. require approval  (Day 2, Block 9)
# --------------------------------------------------------------------------

def require_approval(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    approvals = ctx.get("approvals", {})

    def approved(key: str) -> bool:
        return approvals.get(key) is True

    if request.tool == "change_email" and not approved("change_email"):
        return Decision.hold(
            "approval_required",
            action="change_email",
            why="irreversible account takeover risk",
        )

    if request.tool == "refund_order":
        amount = int(request.args.get("amount_cents", 0))
        if amount > 5000 and not approved("large_refund"):
            return Decision.hold(
                "approval_required", action="refund_order", amount_cents=amount
            )

    return Decision.allow("no_approval_needed")


# --------------------------------------------------------------------------
# 6. rate and action limits  (Day 2, Block 10)
# --------------------------------------------------------------------------

def apply_limits(request: ToolRequest, session: Session, ctx: dict[str, Any]) -> Decision:
    calls = ctx.get("tool_calls_this_turn", 0)
    if calls >= CONFIG.max_tool_calls_per_turn:
        return Decision.deny(
            "rate_limited",
            calls=calls,
            limit=CONFIG.max_tool_calls_per_turn,
        )

    if request.tool == "refund_order":
        spent = db.query(
            "SELECT COALESCE(SUM(amount_cents),0) AS spent FROM refunds"
            " WHERE session_id = ?",
            (session.session_id,),
        )[0]["spent"]
        proposed = spent + int(request.args.get("amount_cents", 0))
        if proposed > CONFIG.max_refund_cents_per_session:
            return Decision.deny(
                "value_limit_exceeded",
                proposed_cents=proposed,
                limit_cents=CONFIG.max_refund_cents_per_session,
            )

    return Decision.allow("within_limits")
