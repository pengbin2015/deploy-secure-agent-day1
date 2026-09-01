"""Kestrel's agent: model, helpers, memory, and the turn pipeline."""

from __future__ import annotations

from typing import Any

from ..controls import profile


def load_helpers() -> dict[str, Any]:
    """Helper agents: the student package, or the mediated reference versions."""
    if profile() == "reference":
        from reference.helpers import HELPERS  # type: ignore
    else:
        from .helpers import HELPERS
    return HELPERS
