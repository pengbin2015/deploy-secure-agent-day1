"""The Attack Board.

Deliberately half automatic. The Kestrel rows are backed by SecurityEvents and
maintain themselves: an attack goes green because a control fired at a surface,
not because someone ticked a box. The My Agent rows are participants reasoning
about their own systems and have no events behind them — automating those would
remove the part of the course that transfers.

    AttackScenario + SecurityEvent  ->  one board row
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..attacks.scenarios import SCENARIOS, AttackScenario
from ..events import DENY, HOLD, LOG
from ..surfaces import SURFACE_NAMES, Surface


@dataclass
class Row:
    attack: str
    entry: int
    stopped_at: int | None
    stopped_by: str | None
    status: str  # "open" | "fixed" | "wrong_control"

    @property
    def entry_label(self) -> str:
        return f"{self.entry} {SURFACE_NAMES[Surface(self.entry)]}"

    @property
    def stopped_label(self) -> str:
        if self.stopped_at is None:
            return "—"
        return f"{self.stopped_at} {SURFACE_NAMES[Surface(self.stopped_at)]}"


def row_for(scenario: AttackScenario) -> Row:
    events = [e for e in LOG.for_scenario(scenario.id)
              if e.decision in (DENY, HOLD)]
    if not events:
        return Row(scenario.title, int(scenario.entry_surface), None, None, "open")
    stop = events[0]
    expected = (stop.control == scenario.expected_control
                and stop.surface == int(scenario.expected_control_surface))
    return Row(scenario.title, int(scenario.entry_surface), stop.surface,
               stop.control, "fixed" if expected else "wrong_control")


def rows(day: int | None = None) -> list[Row]:
    chosen = [s for s in SCENARIOS if day is None or s.day == day]
    return [row_for(s) for s in chosen]


STATUS = {"open": "OPEN", "fixed": "GREEN", "wrong_control": "GREEN?"}


def to_markdown(day: int | None = None) -> str:
    out = ["| Attack | Entry | Stopped at | Stopped by | Status |",
           "| --- | --- | --- | --- | --- |"]
    for r in rows(day):
        out.append(
            f"| {r.attack} | {r.entry_label} | {r.stopped_label} | "
            f"{r.stopped_by or '—'} | {STATUS[r.status]} |"
        )
    out.append("")
    out.append("_Kestrel rows are generated from SecurityEvents. "
               "My Agent rows are yours to fill in._")
    return "\n".join(out)


def to_text(day: int | None = None) -> str:
    lines = [f"{'ATTACK':<38}{'ENTRY':<22}{'STOPPED BY':<24}STATUS", "-" * 96]
    for r in rows(day):
        lines.append(
            f"{r.attack[:36]:<38}{r.entry_label[:20]:<22}"
            f"{(r.stopped_by or '—')[:22]:<24}{STATUS[r.status]}"
        )
    return "\n".join(lines)
