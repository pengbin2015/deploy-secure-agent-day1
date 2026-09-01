"""The controls that live outside the ActionBoundary, gathered in one place.

Intake sits before the model. Result, agent-output and memory controls sit
after the tool. They are separate from the boundary on purpose: the spine slide
shows four zones, and collapsing them into one would teach the wall.
"""

from .intake import Intake, screen
from .results import screen_agent_output, screen_tool_result
from .state import propose_note, recall

__all__ = [
    "Intake", "screen",
    "screen_tool_result", "screen_agent_output",
    "propose_note", "recall",
]
