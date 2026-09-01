"""Kestrel's controls.

Two loaders, matching the two groups on the spine slide:

    load_boundary_controls()   the six checks inside the ActionBoundary
    load_zone_controls()       intake, result, agent-output and memory controls

Both honour KESTREL_CONTROLS=reference so a facilitator can demo the same
attack failing without touching a team's working copy.
"""

from __future__ import annotations

import os
from typing import Any

from ..config import CONFIG


def profile() -> str:
    """Which control set is live, read fresh.

    The console can swap this at runtime for the anchor demo, so it must not be
    captured at import time.
    """
    return os.environ.get("KESTREL_CONTROLS", CONFIG.controls)


def load_boundary_controls() -> Any:
    if profile() == "reference":
        from reference import controls as mod  # type: ignore
    else:
        from . import combined as mod  # type: ignore
    return mod


def load_zone_controls() -> Any:
    if profile() == "reference":
        from reference import zones as mod  # type: ignore
    else:
        from . import zonecontrols as mod  # type: ignore
    return mod
