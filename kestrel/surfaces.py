"""The eight surfaces, and the four control zones laid over them.

This module is the vocabulary for the whole course. Slide "Eight places an
attacker can reach it" is Surface. Slide "Four control zones, one chokepoint"
is Zone. The numbers here are the numbers on the slides, deliberately.
"""

from __future__ import annotations

from enum import IntEnum


class Surface(IntEnum):
    """Where trust can change. Numbered as on the map."""

    USER_MESSAGE = 1
    RETRIEVED_CONTENT = 2
    TOOL_ARGUMENTS = 3
    TOOL_RESULTS = 4
    EXTERNAL_APIS = 5
    OTHER_AGENTS = 6
    STATE_MEMORY = 7
    THE_MODEL = 8


SURFACE_NAMES = {
    Surface.USER_MESSAGE: "User messages",
    Surface.RETRIEVED_CONTENT: "Retrieved content",
    Surface.TOOL_ARGUMENTS: "Tool arguments",
    Surface.TOOL_RESULTS: "Tool results",
    Surface.EXTERNAL_APIS: "External APIs",
    Surface.OTHER_AGENTS: "Other agents",
    Surface.STATE_MEMORY: "State & memory",
    Surface.THE_MODEL: "The model itself",
}

DAY = {
    Surface.USER_MESSAGE: 1,
    Surface.RETRIEVED_CONTENT: 1,
    Surface.TOOL_ARGUMENTS: 1,
    Surface.TOOL_RESULTS: 2,
    Surface.EXTERNAL_APIS: 2,
    Surface.OTHER_AGENTS: 2,
    Surface.STATE_MEMORY: 2,
    Surface.THE_MODEL: 2,
}


class Zone:
    """Where software intervenes. Four zones, one of them a chokepoint.

    These do not replace the surface map. They say where we enforce on it.
    """

    INTAKE = "intake"
    ACTION = "action"
    RESULT_STATE = "result_state"
    OBSERVE = "observe"


ZONE_NAMES = {
    Zone.INTAKE: "Intake controls",
    Zone.ACTION: "Action boundary",
    Zone.RESULT_STATE: "Result & state controls",
    Zone.OBSERVE: "Observe & verify",
}

# Which surfaces each zone is responsible for. Note that no zone covers all of
# them: that is the point. Surfaces 5 and 6 cross further trust boundaries and
# are handled by their own controls on Day 2.
ZONE_SURFACES = {
    Zone.INTAKE: (Surface.USER_MESSAGE, Surface.RETRIEVED_CONTENT),
    Zone.ACTION: (Surface.TOOL_ARGUMENTS,),
    Zone.RESULT_STATE: (
        Surface.TOOL_RESULTS,
        Surface.EXTERNAL_APIS,
        Surface.OTHER_AGENTS,
        Surface.STATE_MEMORY,
    ),
    Zone.OBSERVE: tuple(Surface),
}


def zone_for(surface: Surface) -> str:
    """The zone that enforces at this surface."""
    for zone in (Zone.INTAKE, Zone.ACTION, Zone.RESULT_STATE):
        if surface in ZONE_SURFACES[zone]:
            return zone
    return Zone.OBSERVE


def describe(surface: Surface) -> str:
    return f"{int(surface)} {SURFACE_NAMES[surface]}"
