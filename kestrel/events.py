"""SecurityEvent and the log that collects it.

A SecurityEvent is not a log line. It is a teaching-level statement about which
engineering guarantee held or failed, and it is the thing the control room, the
Attack Board and the Evidence C invariant are all built on.

Two consumers, deliberately separate:

    SecurityEvent ---> the control room   (which boundary held?)
                  \\--> Langfuse           (what happened in this run?)

If Langfuse is ever replaced, nothing about the course changes.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Iterable

from .surfaces import Surface, zone_for

ALLOW = "allow"
DENY = "deny"
HOLD = "hold"  # held for a human decision (Day 2, Block 9)
BREACH = "breach"  # observed by a detector after unsafe data escaped


@dataclass(frozen=True)
class SecurityEvent:
    """One boundary decision.

    surface is where the control was *exercised*, not where the attack entered.
    An attack can arrive at surface 1 and be stopped at surface 3; the scenario
    records the entry point, the event records the enforcement point.
    """

    surface: int
    control: str
    decision: str
    reason: str
    zone: str = ""
    tool: str | None = None
    session_id: str | None = None
    scenario_id: str | None = None
    turn_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.zone:
            object.__setattr__(self, "zone", zone_for(Surface(self.surface)))
        if self.decision not in (ALLOW, DENY, HOLD, BREACH):
            raise ValueError(
                f"decision must be allow/deny/hold/breach, got {self.decision!r}"
            )

    @property
    def held(self) -> bool:
        """True when the control did its job: it either allowed or refused."""
        return self.decision in (DENY, HOLD)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        mark = {ALLOW: "allow", DENY: "DENY", HOLD: "HOLD", BREACH: "BREACHED"}[
            self.decision
        ]
        tool = f" {self.tool}" if self.tool else ""
        return f"[s{self.surface} {self.control}]{tool} {mark} — {self.reason}"


class EventLog:
    """Collects events for one process and fans them out to subscribers."""

    def __init__(self) -> None:
        self._events: list[SecurityEvent] = []
        self._subscribers: list[Callable[[SecurityEvent], None]] = []

    def subscribe(self, fn: Callable[[SecurityEvent], None]) -> None:
        self._subscribers.append(fn)

    def emit(self, event: SecurityEvent) -> SecurityEvent:
        self._events.append(event)
        for fn in self._subscribers:
            try:
                fn(event)
            except Exception:  # a broken sink must never break the boundary
                pass
        return event

    # -- reading -----------------------------------------------------------
    def all(self) -> list[SecurityEvent]:
        return list(self._events)

    def for_turn(self, turn_id: str) -> list[SecurityEvent]:
        return [e for e in self._events if e.turn_id == turn_id]

    def for_scenario(self, scenario_id: str) -> list[SecurityEvent]:
        return [e for e in self._events if e.scenario_id == scenario_id]

    def denials(self) -> list[SecurityEvent]:
        return [e for e in self._events if e.decision in (DENY, HOLD)]

    def pop(self) -> SecurityEvent | None:
        return self._events.pop() if self._events else None

    def clear(self) -> None:
        self._events.clear()

    def to_json(self) -> str:
        return json.dumps([e.as_dict() for e in self._events], indent=2)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterable[SecurityEvent]:
        return iter(self._events)


def new_turn_id() -> str:
    return uuid.uuid4().hex[:12]


#: Process-wide log. Kestrel is a teaching app running one classroom session at
#: a time; a module-level log keeps the code readable. A real system would pass
#: this explicitly.
LOG = EventLog()
