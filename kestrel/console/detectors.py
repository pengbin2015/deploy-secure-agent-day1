"""Detectors: observers, not controls.

A control decides whether something happens. A detector notices that it did.
Nothing in this module prevents anything, and that is the point — it is what
makes the anchor breach *visible* on a build that has no controls at all.

Slide "Where it actually happened" walks the breach back with the data-boundary
light red. On a fresh clone every control returns `not_implemented`, so nothing
can honestly go red by refusing. The detector fills that gap the honest way: it
watches what left the tool and says a boundary was crossed.

This is also Day 2, Block 8 arriving early. Prevention and detection are
different jobs, and the console shows them in different places:

    Action boundary   NOT WIRED     <- no control ran
    DATA BOUNDARY     BREACHED      <- and here is what got out
"""

from __future__ import annotations

from typing import Any

from ..events import ALLOW, BREACH, LOG, SecurityEvent
from ..surfaces import Surface

DATA_BOUNDARY = "data_boundary"


def _rows(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        return [result]
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    return []


def check_data_boundary(tool: str, result: Any, session: Any, *,
                        turn_id: str | None = None,
                        scenario_id: str | None = None) -> bool:
    """Did data belonging to someone other than the caller leave this tool?

    Returns True when a breach was observed. The caller does nothing with that
    return value except carry on, because a detector that changed behaviour
    would be a control wearing a disguise.
    """
    owners: set[int] = set()
    for row in _rows(result):
        owner = row.get("customer_id")
        if isinstance(owner, int):
            owners.add(owner)

    foreign = {o for o in owners if o != getattr(session, "customer_id", None)}
    if not foreign:
        return False

    LOG.emit(
        SecurityEvent(
            surface=int(Surface.TOOL_RESULTS),
            control=DATA_BOUNDARY,
            decision=BREACH,
            reason="cross_tenant_data_in_result",
            tool=tool,
            session_id=getattr(session, "session_id", None),
            scenario_id=scenario_id,
            turn_id=turn_id,
            detail={
                "session_customer": getattr(session, "customer_id", None),
                "customers_in_result": sorted(foreign),
                "rows": len(_rows(result)),
                "observed_only": True,
            },
        )
    )
    return True
