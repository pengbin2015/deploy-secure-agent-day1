"""Kestrel — a deliberately breakable customer-support agent.

Teaching application for "Developing Secure AI Agents" (NUS-ISS).

    Assume the model is already compromised.
    Constrain what it can reach and do.

Core is stdlib only. LangGraph, Langfuse and a live model are all optional.
"""

__version__ = "1.0.0"

from .surfaces import Surface, Zone  # noqa: F401
from .events import SecurityEvent, LOG  # noqa: F401
