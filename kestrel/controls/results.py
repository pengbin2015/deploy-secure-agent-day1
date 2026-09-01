"""Result controls — surface 4, and what comes back from surfaces 5 and 6.
(Day 2, Blocks 6 and 7)

A tool result is not trusted data. It is a payload written by whoever last
touched the row, the API, or the other agent. Validate what comes back, not
just what goes in — otherwise a compromised supplier becomes an injection
channel straight into the model's context.

WORKSHOP 2 — implement these.
"""

from __future__ import annotations

from typing import Any

from ..events import ALLOW, DENY, LOG, SecurityEvent
from ..surfaces import Surface


def screen_tool_result(tool: str, result: Any, *, surface: int = int(Surface.TOOL_RESULTS),
                       turn_id: str | None = None, session_id: str | None = None,
                       scenario_id: str | None = None) -> Any:
    """Quarantine or neutralise attacker-controlled text before it re-enters
    the model's context."""
    # TODO(Day 2, Block 7): wrap untrusted result text so the model reads it as
    # data, strip or flag instruction-shaped content, and emit an event when you
    # do. The event is what turns the console red.
    LOG.emit(
        SecurityEvent(
            surface=surface,
            control="result_screen",
            decision=ALLOW,
            reason="not_implemented",
            tool=tool,
            session_id=session_id,
            scenario_id=scenario_id,
            turn_id=turn_id,
        )
    )
    return result


def screen_agent_output(agent_name: str, output: str, *, turn_id: str | None = None,
                        session_id: str | None = None,
                        scenario_id: str | None = None) -> str:
    """A helper agent's answer inherits no authority from the agent that asked."""
    # TODO(Day 2, Block 6): quarantine helper output. A summary from a helper is
    # a claim, not an instruction, and it must not be able to widen what the
    # main agent is permitted to do.
    LOG.emit(
        SecurityEvent(
            surface=int(Surface.OTHER_AGENTS),
            control="agent_output_screen",
            decision=ALLOW,
            reason="not_implemented",
            tool=agent_name,
            session_id=session_id,
            scenario_id=scenario_id,
            turn_id=turn_id,
        )
    )
    return output
