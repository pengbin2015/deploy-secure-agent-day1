"""Kestrel's two helper agents.  (Day 2, Block 6)

Both are "internal", which is exactly why they are dangerous. A helper is
another place the model's context can be written by someone else, and its
answer arrives wearing the same clothes as everything else in the prompt.

There is also a live bug in here, deliberately. ``summarise_orders`` reaches
straight for the tool registry instead of going through the ActionBoundary —
the way a developer reuses a function and forgets the thing wrapped around it.
Every Evidence B case can pass while this is present. Evidence C is what
catches it.
"""

from __future__ import annotations

from typing import Any

from .. import db
from ..tools.registry import REGISTRY


def summarise_orders(customer_id: int, session: Any = None,
                     boundary: Any = None) -> str:
    """Summarise a customer's recent orders for the main agent.

    The session and boundary are handed in and then ignored, which is exactly
    how this bug looks in a real codebase.
    """
    # TODO(Workshop 1, Phase C): this bypasses the ActionBoundary entirely.
    # Route it through boundary.execute with the caller's session, or stop
    # calling a tool from here at all. Until then `evidence c` fails, and it
    # should.
    rows = REGISTRY.invoke("list_my_orders", {"customer_id": customer_id})
    if not rows:
        return "No recent orders."
    return "; ".join(f"{r['id']} {r['item']} ({r['status']})" for r in rows)


def lookup_policy(question: str) -> str:
    """Search the help centre and summarise. Returns UNTRUSTED text.

    Whatever is in those documents is now in the main agent's context. That is
    surface 2 arriving through surface 6.
    """
    rows = db.query("SELECT title, body FROM help_docs")
    hits = [r for r in rows if any(w in r["body"].lower()
                                   for w in question.lower().split() if len(w) > 4)]
    chosen = hits or rows[:1]
    return "\n".join(f"{r['title']}: {r['body']}" for r in chosen)


HELPERS = {"summarise_orders": summarise_orders, "lookup_policy": lookup_policy}
