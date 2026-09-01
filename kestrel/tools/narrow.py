"""The narrow tools. One verb each, every parameter typed and bounded.

This is where Workshop 1 Phase B lands. Compare the two signatures:

    lookup_orders(sql: str)                 # can express this morning's attack
    get_order(order_id: int)                # cannot express it at all

The second is not "better validated". The malicious call has no grammar in
which to be written. That is the difference between narrowing a tool and
guarding one.

Note also what these do NOT do: they take no session, do no authorization and
read no policy. Deciding *whether* is the ActionBoundary's job. A tool that
authorizes itself is a tool you have to audit once per tool.
"""

from __future__ import annotations

import time
from typing import Any

from .. import db
from .registry import Param, ToolError, ToolSpec

EMAIL = r"[^@\s]{1,64}@[^@\s]{1,180}\.[A-Za-z]{2,10}"


def get_shipping_address(order_id: int) -> dict[str, Any]:
    rows = db.query(
        "SELECT o.id, o.ship_to, c.name AS customer_name"
        " FROM orders o JOIN customers c ON c.id = o.customer_id"
        " WHERE o.id = ?",
        (order_id,),
    )
    if not rows:
        raise ToolError("no such order")
    return {
        "order_id": order_id,
        "ship_to": rows[0]["ship_to"],
        "customer_name": rows[0]["customer_name"],
    }


def get_order(order_id: int) -> dict[str, Any]:
    rows = db.query(
        "SELECT id, customer_id, item, total_cents, status FROM orders WHERE id = ?",
        (order_id,),
    )
    if not rows:
        raise ToolError("no such order")
    return rows[0]


def get_order_note(order_id: int) -> dict[str, Any]:
    """Read the gift note. Separate from get_order because it returns
    attacker-controllable text and therefore crosses surface 4."""
    rows = db.query("SELECT id, gift_note FROM orders WHERE id = ?", (order_id,))
    if not rows:
        raise ToolError("no such order")
    return {"order_id": order_id, "note": rows[0]["gift_note"], "untrusted": True}


def list_my_orders(customer_id: int) -> list[dict[str, Any]]:
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


def cancel_order(order_id: int) -> dict[str, Any]:
    db.execute("UPDATE orders SET status='cancelled' WHERE id = ?", (order_id,))
    return {"order_id": order_id, "status": "cancelled"}


def change_email(customer_id: int, new_email: str) -> dict[str, Any]:
    db.execute("UPDATE customers SET email = ? WHERE id = ?", (new_email, customer_id))
    return {"customer_id": customer_id, "email": new_email}


def apply_discount(order_id: int, percent: int) -> dict[str, Any]:
    rows = db.query("SELECT total_cents FROM orders WHERE id = ?", (order_id,))
    if not rows:
        raise ToolError("no such order")
    total = int(rows[0]["total_cents"])
    off = total * percent // 100
    db.execute("UPDATE orders SET total_cents = ? WHERE id = ?", (total - off, order_id))
    return {"order_id": order_id, "percent": percent, "discount_cents": off}


SPECS = [
    ToolSpec(
        name="get_shipping_address",
        fn=get_shipping_address,
        params={"order_id": Param(int, minimum=1, maximum=9_999_999)},
        description="Get the shipping address for an order.",
    ),
    ToolSpec(
        name="get_order",
        fn=get_order,
        params={"order_id": Param(int, minimum=1, maximum=9_999_999)},
        description="Read one order by id.",
    ),
    ToolSpec(
        name="get_order_note",
        fn=get_order_note,
        params={"order_id": Param(int, minimum=1, maximum=9_999_999)},
        description="Read the gift note on an order. Returns untrusted text.",
    ),
    ToolSpec(
        name="list_my_orders",
        fn=list_my_orders,
        params={"customer_id": Param(int, minimum=1, maximum=9_999_999)},
        description="List the orders belonging to one customer.",
    ),
    ToolSpec(
        name="refund_order",
        fn=refund_order,
        params={
            "order_id": Param(int, minimum=1, maximum=9_999_999),
            "amount_cents": Param(int, minimum=1, maximum=100_000),
            "session_id": Param(str, required=False, max_len=64),
        },
        side_effect=True,
        description="Refund an amount against one order.",
    ),
    ToolSpec(
        name="cancel_order",
        fn=cancel_order,
        params={"order_id": Param(int, minimum=1, maximum=9_999_999)},
        side_effect=True,
        description="Cancel one order.",
    ),
    ToolSpec(
        name="apply_discount",
        fn=apply_discount,
        params={
            "order_id": Param(int, minimum=1, maximum=9_999_999),
            "percent": Param(int, minimum=1, maximum=50),
        },
        side_effect=True,
        description="Apply a percentage discount to one order.",
    ),
    ToolSpec(
        name="change_email",
        fn=change_email,
        params={
            "customer_id": Param(int, minimum=1, maximum=9_999_999),
            "new_email": Param(str, max_len=254, pattern=EMAIL),
        },
        side_effect=True,
        description="Change the email on one account.",
    ),
]
