"""Intake controls — surfaces 1 and 2, before the model.  (Day 1, Block 2)

These are NOT part of the ActionBoundary and they are not a wall. They raise
the attacker's cost and they produce signal. Everything they miss is exactly
what the rest of the day is for.

Three layers, cheapest first: structural, content, semantic.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

from ..events import ALLOW, DENY, LOG, SecurityEvent
from ..surfaces import Surface

MAX_MESSAGE_CHARS = 4000

# Known injection shapes — a denylist, named as one. Catches the careless
# attacker; a determined one only has to rephrase.
_INJECTION_SHAPES = [
    r"ignore (all )?(your )?previous instructions",
    r"disregard (the )?(above|prior|previous)",
    r"you are now (in )?\w+ mode",
    r"system\s*note\s*:",
    r"\[\[.*?\]\]",
    r"<\s*/?\s*(system|instructions?)\s*>",
]

# Control characters that structural parsers treat as terminators or NUL
# injections, but that a plain string comparison silently swallows.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Intake:
    """A piece of content arriving at the agent, with its provenance kept."""

    text: str
    surface: int
    trusted: bool = False
    flags: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return "trusted" if self.trusted else "untrusted"


def screen(item: Intake, *, turn_id: str | None = None, session_id: str | None = None,
           scenario_id: str | None = None, tool: str | None = None) -> Intake:
    """Screen one piece of incoming content and emit an event either way."""
    decision, reason, flags = _inspect(item)
    item.flags = flags
    LOG.emit(
        SecurityEvent(
            surface=item.surface,
            control="input_validation",
            decision=decision,
            reason=reason,
            session_id=session_id,
            scenario_id=scenario_id,
            turn_id=turn_id,
            tool=tool,
            detail={"flags": flags, "chars": len(item.text)},
        )
    )
    if decision == DENY:
        item.text = "[content withheld by intake controls]"
    return item


def _contains_encoded_instruction(text: str) -> bool:
    """Return True if text is valid base64 that decodes to a known injection shape."""
    if not re.fullmatch(r"[A-Za-z0-9+/=]{16,}", text):
        return False
    try:
        decoded = base64.b64decode(text, validate=True).decode("utf-8").lower()
    except (UnicodeDecodeError, ValueError):
        return False
    return any(re.search(pattern, decoded) for pattern in _INJECTION_SHAPES)


def _semantic_verdict(text: str) -> str | None:
    """Call the gateway classifier. Returns None when no gateway is configured."""
    from ..agent.llm import GatewayModel
    from ..config import CONFIG

    if CONFIG.llm != "gateway" or not CONFIG.llm_base_url or not CONFIG.llm_api_key:
        return None
    try:
        return GatewayModel().classify_intake(text)
    except Exception:
        return None


def _inspect(item: Intake) -> tuple[str, str, list[str]]:
    text = item.text or ""
    flags: list[str] = []

    # Layer 1 — structural. Cheap and deterministic; runs before any parsing.
    if len(text) > MAX_MESSAGE_CHARS:
        return DENY, "oversize_input", ["length"]
    if _CONTROL_CHARS.search(text):
        return DENY, "control_characters", ["encoding"]

    # Layer 2 — content. Flags known injection shapes and encoded variants.
    # Does not block retrieved content: the attacker only needs to rephrase,
    # and blocking help-centre docs on the word "system" breaks the product.
    low = text.lower()
    for pattern in _INJECTION_SHAPES:
        if re.search(pattern, low):
            flags.append("injection_shape")
            break
    if _contains_encoded_instruction(text):
        flags.append("encoded_instruction")

    if flags and item.surface == int(Surface.USER_MESSAGE):
        return DENY, "injection_shape_in_user_message", flags
    if flags:
        # Retrieved content keeps its provenance and travels on, marked.
        return ALLOW, "flagged_untrusted_content", flags

    # Layer 3 — semantic. Last because it is the only paid, fallible check.
    # Only applied to user messages; retrieved content is not user intent.
    verdict = _semantic_verdict(text) if item.surface == int(Surface.USER_MESSAGE) else "CLEAR"
    if verdict is None:
        return ALLOW, "semantic_layer_unavailable", flags
    if verdict == "SUSPICIOUS":
        return DENY, "semantic_intent_flagged", ["semantic_intent"]
    return ALLOW, "clean", flags
