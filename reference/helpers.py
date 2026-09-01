"""Helper agents, with the mediation bug fixed.

The difference is one line, and it is the whole of Evidence C: the helper asks
the ActionBoundary instead of reaching for the tool registry. The helper does
not get to decide that its own call is safe, any more than the model does.
"""

from __future__ import annotations

from typing import Any

from kestrel import db
from kestrel.agent.helpers import lookup_policy
from kestrel.boundary import ToolRequest
from kestrel.surfaces import Surface


def summarise_orders(customer_id: int, session: Any = None,
                     boundary: Any = None) -> str:
    if session is None or boundary is None:
        return "No recent orders."
    outcome = boundary.execute(
        ToolRequest("list_my_orders", {"customer_id": customer_id},
                    origin_surface=int(Surface.OTHER_AGENTS)),
        session,
    )
    if not outcome.allowed:
        return "Order summary unavailable."
    rows = outcome.result or []
    if not rows:
        return "No recent orders."
    return "; ".join(f"{r['id']} {r['item']} ({r['status']})" for r in rows)


HELPERS = {"summarise_orders": summarise_orders, "lookup_policy": lookup_policy}
