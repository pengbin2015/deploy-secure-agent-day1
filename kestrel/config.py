"""Configuration. Everything comes from the environment or has a safe default.

Nothing here needs the network. Kestrel runs offline with a scripted model so
that the deterministic evidence (B and C) never depends on a live API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@dataclass
class Config:
    # -- where the controls live ------------------------------------------
    # "student"   the stubs teams fill in during the workshops (default)
    # "reference" the completed implementations, for the facilitator's demos
    controls: str = field(default_factory=lambda: _env("KESTREL_CONTROLS", "student"))

    # -- the model ---------------------------------------------------------
    # "scripted"  deterministic, offline, no key needed. Used by all tests.
    # "gateway"   OpenAI-compatible endpoint (LiteLLM proxy, per-team key)
    llm: str = field(default_factory=lambda: _env("KESTREL_LLM", "scripted"))
    llm_base_url: str = field(default_factory=lambda: _env("KESTREL_LLM_BASE_URL"))
    llm_api_key: str = field(default_factory=lambda: _env("KESTREL_LLM_API_KEY"))
    llm_model: str = field(default_factory=lambda: _env("KESTREL_LLM_MODEL", "gpt-4o-mini"))
    llm_timeout: int = field(default_factory=lambda: _env_int("KESTREL_LLM_TIMEOUT", 30))

    # -- data --------------------------------------------------------------
    db_path: str = field(default_factory=lambda: _env("KESTREL_DB", str(ROOT / "kestrel.db")))

    # -- traces (optional) -------------------------------------------------
    langfuse_host: str = field(default_factory=lambda: _env("LANGFUSE_HOST"))
    langfuse_public_key: str = field(default_factory=lambda: _env("LANGFUSE_PUBLIC_KEY"))
    langfuse_secret_key: str = field(default_factory=lambda: _env("LANGFUSE_SECRET_KEY"))

    # -- control room ------------------------------------------------------
    console_port: int = field(default_factory=lambda: _env_int("KESTREL_CONSOLE_PORT", 8899))

    # -- limits (Day 2, Block 10) -----------------------------------------
    max_tool_calls_per_turn: int = field(
        default_factory=lambda: _env_int("KESTREL_MAX_TOOL_CALLS", 6)
    )
    max_refund_cents_per_session: int = field(
        default_factory=lambda: _env_int("KESTREL_MAX_REFUND_CENTS", 20000)
    )

    team: str = field(default_factory=lambda: _env("KESTREL_TEAM", "team-0"))

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_host and self.langfuse_public_key)

    @property
    def using_reference_controls(self) -> bool:
        return self.controls == "reference"


CONFIG = Config()


def reload() -> Config:
    """Re-read the environment. Used by tests that flip KESTREL_CONTROLS."""
    global CONFIG
    CONFIG = Config()
    return CONFIG
