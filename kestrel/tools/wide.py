"""The tools Kestrel ships with. These are deliberately wide.

Every anti-pattern from the Block 3 slide is here on purpose:

  lookup_orders(sql)          free-form query string — a blank cheque
  account_action(action, ...) one tool, many behaviours — the god tool
  fetch_and_refund(order_id)  reads untrusted content AND takes a side effect

Teams replace these in Workshop 1 Phase B. The point is not that the code is
bad; it is that no amount of care at the boundary can make ``sql: str``
expressible only in safe ways.
"""

from __future__ import annotations

import time
from typing import Any

from .. import db
from .registry import Param, ToolSpec


def lookup_orders(sql: str) -> list[dict[str, Any]]:
    """Run a query against the orders database. Whatever query you like."""
    return db.query(sql)


def account_action(action: str, target_id: int, value: str = "") -> dict[str, Any]:
    """One tool, four behaviours, chosen by a string the model controls."""
    if action == "get_order":
        rows = db.query("SELECT * FROM orders WHERE id = ?", (target_id,))
        return rows[0] if rows else {}
    if action == "cancel_order":
        db.execute("UPDATE orders SET status='cancelled' WHERE id = ?", (target_id,))
        return {"order_id": target_id, "status": "cancelled"}
    if action == "change_email":
        db.execute("UPDATE customers SET email = ? WHERE id = ?", (value, target_id))
        return {"customer_id": target_id, "email": value}
    if action == "refund":
        amount = int(value or 0)
        db.execute(
            "INSERT INTO refunds (order_id, amount_cents, session_id, created_at)"
            " VALUES (?,?,?,?)",
            (target_id, amount, "unknown", time.time()),
        )
        return {"order_id": target_id, "refunded_cents": amount}
    raise ValueError(f"unknown action {action!r}")


def fetch_and_refund(order_id: int) -> dict[str, Any]:
    """Read the order, including its gift note, and refund it in one step.

    Read and act fused together, with no gate in between. Whatever the gift
    note says has already influenced the refund by the time anyone could check.
    """
    rows = db.query("SELECT * FROM orders WHERE id = ?", (order_id,))
    if not rows:
        raise ValueError("no such order")
    order = rows[0]
    db.execute(
        "INSERT INTO refunds (order_id, amount_cents, session_id, created_at)"
        " VALUES (?,?,?,?)",
        (order_id, order["total_cents"], "unknown", time.time()),
    )
    return {
        "order_id": order_id,
        "refunded_cents": order["total_cents"],
        "gift_note": order["gift_note"],
    }


def change_email(customer_id: int, new_email: str) -> dict[str, Any]:
    db.execute("UPDATE customers SET email = ? WHERE id = ?", (new_email, customer_id))
    return {"customer_id": customer_id, "email": new_email}


def apply_discount(order_id: int, percent: int) -> dict[str, Any]:
    rows = db.query("SELECT total_cents FROM orders WHERE id = ?", (order_id,))
    if not rows:
        raise ValueError("no such order")
    total = int(rows[0]["total_cents"])
    off = total * percent // 100
    db.execute("UPDATE orders SET total_cents = ? WHERE id = ?", (total - off, order_id))
    return {"order_id": order_id, "percent": percent, "discount_cents": off}


def list_my_orders(customer_id: int) -> list[dict[str, Any]]:
    """List a customer's orders.

    A perfectly ordinary tool, and the one the anchor breach goes through. The
    customer_id comes from the model, not from the session, and the query never
    asks whose orders these are.
    """
    return db.query(
        "SELECT o.id, o.customer_id, c.name AS customer_name, o.item,"
        " o.total_cents, o.status, o.ship_to"
        " FROM orders o JOIN customers c ON c.id = o.customer_id"
        " WHERE o.customer_id = ? ORDER BY o.id",
        (customer_id,),
    )


def refund_order(order_id: int, amount_cents: int, session_id: str = "") -> dict[str, Any]:
    db.execute(
        "INSERT INTO refunds (order_id, amount_cents, session_id, created_at)"
        " VALUES (?,?,?,?)",
        (order_id, amount_cents, session_id, time.time()),
    )
    return {"order_id": order_id, "refunded_cents": amount_cents}


SPECS = [
    ToolSpec(
        name="lookup_orders",
        fn=lookup_orders,
        params={"sql": Param(str, max_len=4000)},
        description="Query the orders database.",
        wide=True,
    ),
    ToolSpec(
        name="account_action",
        fn=account_action,
        params={
            "action": Param(str, max_len=64),
            "target_id": Param(int),
            "value": Param(str, required=False, max_len=512),
        },
        side_effect=True,
        description="Perform an account action.",
        wide=True,
    ),
    ToolSpec(
        name="fetch_and_refund",
        fn=fetch_and_refund,
        params={"order_id": Param(int)},
        side_effect=True,
        description="Look up an order and refund it.",
        wide=True,
    ),
    ToolSpec(
        name="change_email",
        fn=change_email,
        params={"customer_id": Param(int), "new_email": Param(str, max_len=254)},
        side_effect=True,
        description="Change the email on an account.",
        wide=True,
    ),
    ToolSpec(
        name="apply_discount",
        fn=apply_discount,
        params={"order_id": Param(int), "percent": Param(int)},
        side_effect=True,
        description="Apply a percentage discount to an order.",
        wide=True,
    ),
    # Not marked wide: the shape of this tool is fine. What is missing is any
    # check that the customer_id belongs to the caller — which is the anchor.
    ToolSpec(
        name="list_my_orders",
        fn=list_my_orders,
        params={"customer_id": Param(int)},
        description="List the orders belonging to one customer.",
    ),
    ToolSpec(
        name="refund_order",
        fn=refund_order,
        params={
            "order_id": Param(int),
            "amount_cents": Param(int),
            "session_id": Param(str, required=False, max_len=64),
        },
        side_effect=True,
        description="Refund an amount against one order.",
    ),
]
