"""The control room.

Langfuse answers "what happened inside this run". This answers the only
question a beginner can act on in the first hour: which engineering guarantee
held, and which one failed.

Four zones, one line each, driven entirely by SecurityEvents. If a zone has no
events it is DARK — not green. A control that never ran is not a control that
passed, and the difference is most of Day 2.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..events import ALLOW, BREACH, DENY, HOLD, LOG, SecurityEvent
from ..surfaces import Zone, ZONE_NAMES, Surface, zone_for
from .detectors import DATA_BOUNDARY

#: Zone states. Note that a control which REFUSES an attack has done its job,
#: so it is not red. Red is reserved for the detectors: it means something
#: actually got out. That is the light slide "Where it actually happened" wants.
GREEN, REFUSED, AMBER, DARK = "green", "refused", "amber", "dark"
RED = "red"   # detectors only

_ANSI = {
    GREEN: "\033[92m", REFUSED: "\033[96m", RED: "\033[91m",
    AMBER: "\033[93m", DARK: "\033[90m",
    "reset": "\033[0m", "bold": "\033[1m",
}

ZONE_ORDER = (Zone.INTAKE, Zone.ACTION, Zone.RESULT_STATE, Zone.OBSERVE)


def zone_state(events: Iterable[SecurityEvent],
               mediation: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Reduce a stream of events to one status per zone.

    Precedence is deliberate: red beats amber beats dark beats green. A zone
    holding one unimplemented control is NOT WIRED, however many other checks
    passed — otherwise the panel shows a comforting green for a gap, which is
    the one thing a security console must never do.
    """
    state = {
        z: {"zone": z, "name": ZONE_NAMES[z], "status": DARK,
            "controls": [], "last": "", "_deny": False, "_hold": False,
            "_gap": False, "_ok": False}
        for z in ZONE_ORDER
    }
    for e in events:
        if e.control == DATA_BOUNDARY:
            continue  # a detector observed a breach; no control decided here
        z = e.zone if e.zone in state else zone_for(Surface(e.surface))
        cell = state[z]
        cell["controls"].append(
            {"control": e.control, "decision": e.decision, "reason": e.reason,
             "surface": e.surface, "tool": e.tool}
        )
        cell["last"] = f"{e.control}: {e.reason}"
        if e.decision == DENY:
            cell["_deny"] = True
        elif e.decision == HOLD:
            cell["_hold"] = True
        elif e.reason == "not_implemented":
            cell["_gap"] = True
        else:
            cell["_ok"] = True

    # Observe & verify is not driven by surface events: it is the invariant.
    obs = state[Zone.OBSERVE]
    if mediation is not None:
        n = mediation.get("total_invocations", 0)
        if n == 0:
            obs["_gap"] = True
            obs["last"] = "no tool calls — invariant not exercised"
        elif mediation.get("holds"):
            obs["_ok"] = True
            obs["last"] = f"mediation holds over {n} tool calls"
        else:
            obs["_gap"] = True
            obs["last"] = "unmediated tool call"
    elif events:
        obs["_gap"] = True
        obs["last"] = "no mediation report"

    for cell in state.values():
        if cell["_deny"]:
            cell["status"] = REFUSED
        elif cell["_hold"]:
            cell["status"] = AMBER
        elif cell["_gap"] or not cell["_ok"]:
            cell["status"] = DARK
        else:
            cell["status"] = GREEN
        for k in ("_deny", "_hold", "_gap", "_ok"):
            cell.pop(k)
    return state


def breaches(events: Iterable[SecurityEvent]) -> list[SecurityEvent]:
    """What the detectors observed. Separate from the zones because a breach
    that nothing refused is a different fact from a control that refused."""
    return [e for e in events
            if e.control == DATA_BOUNDARY and e.decision == BREACH]


def render(events: Iterable[SecurityEvent] | None = None, *,
           mediation: dict[str, Any] | None = None, colour: bool = True) -> str:
    events = list(events if events is not None else LOG.all())
    state = zone_state(events, mediation)
    width = 62

    def paint(text: str, key: str) -> str:
        if not colour:
            return text
        return f"{_ANSI[key]}{text}{_ANSI['reset']}"

    lines = ["", "  KESTREL CONTROL ROOM".ljust(width), "  " + "-" * (width - 4)]
    label = {GREEN: "CLEAR", REFUSED: "REFUSED", AMBER: "AWAITING APPROVAL",
             DARK: "NOT WIRED"}
    for z in ZONE_ORDER:
        cell = state[z]
        dot = {GREEN: "*", REFUSED: "+", AMBER: "!", DARK: "."}[cell["status"]]
        name = cell["name"].ljust(26)
        status = label[cell["status"]].ljust(18)
        lines.append("  " + paint(f"{dot} {name}{status}", cell["status"])
                     + f" {cell['last'][:40]}")

    seen = breaches(events)
    if seen:
        who = sorted({c for e in seen
                      for c in e.detail.get("customers_in_result", [])})
        lines += [
            "  " + "-" * (width - 4),
            "  " + paint("X DATA BOUNDARY             BREACHED", RED)
            + f"        another customer's data left the tool: {who}",
        ]

    if mediation is not None:
        ok = mediation.get("holds", False)
        n = mediation.get("total_invocations", 0)
        if ok:
            msg = f"mediation invariant holds — {n} tool calls, all through the boundary"
            lines += ["  " + "-" * (width - 4), "  " + paint(msg, GREEN)]
        else:
            bad = {o["tool"] for o in mediation.get("unmediated", [])}
            msg = (f"MEDIATION BROKEN — {len(mediation['unmediated'])} of {n} calls "
                   f"bypassed the boundary: {', '.join(sorted(bad))}")
            lines += ["  " + "-" * (width - 4), "  " + paint(msg, RED)]
    lines.append("")
    return "\n".join(lines)


def snapshot(boundary: Any = None) -> dict[str, Any]:
    """JSON for the browser panel."""
    events = LOG.all()
    med = boundary.mediation_report() if boundary else None
    return {
        "zones": list(zone_state(events, med).values()),
        "breaches": [e.as_dict() for e in breaches(events)],
        "events": [e.as_dict() for e in events[-60:]],
        "mediation": med,
        "count": len(events),
    }
