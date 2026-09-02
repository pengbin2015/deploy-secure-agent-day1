"""FastAPI backend for the Kestrel control room.

    python -m kestrel console      API on :8899, UI on :8501

Endpoints:

    GET  /api/state        zones, breaches, mediation, recent events
    GET  /api/scenarios    the attack corpus, for the dropdown
    POST /api/chat         {"message": "..."}  -> one turn
    POST /api/attack       {"id": "..."}       -> run a scenario
    POST /api/reset        clear the event log and reseed
    POST /api/profile      facilitator: swap student <-> reference controls
"""

from __future__ import annotations

import os
import threading
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .. import db
from ..boundary import ActionBoundary, Session
from ..config import CONFIG, reload as reload_config
from ..controls import profile as live_profile
from ..events import LOG
from ..tools.registry import REGISTRY
from .panel import snapshot

#: One shopper for the class. Amara is customer 1001; everything she is
#: entitled to see belongs to 1001, which is what makes the leak legible.
SHOPPER = {"session_id": "web-chat", "customer_id": 1001, "roles": ("customer",)}


class Room:
    """The agent and boundary the page talks to. Rebuilt when the profile swaps."""

    def __init__(self, narrow: bool = False) -> None:
        self.narrow = narrow
        self.lock = threading.Lock()
        self.build()

    def build(self) -> None:
        from ..agent.graph import Kestrel

        reload_config()
        if self.narrow:
            from ..tools import narrow as mod
        else:
            from ..tools import wide as mod
        REGISTRY.replace_all(list(mod.SPECS))
        REGISTRY.reset_invocations()
        self.boundary = ActionBoundary()
        self.agent = Kestrel(boundary=self.boundary)

    def session(self) -> Session:
        return Session(SHOPPER["session_id"], SHOPPER["customer_id"],
                       tuple(SHOPPER["roles"]))

    def turn(self, message: str, scenario_id: str | None = None) -> dict[str, Any]:
        with self.lock:
            t = self.agent.handle(message, self.session(), scenario_id=scenario_id)
            return {
                "reply": t.reply,
                "executed": [e["tool"] for e in t.executed],
                "refused": t.refused,
            }

    def beat_validator(self) -> dict[str, Any]:
        from ..__main__ import run_beat_validator

        with self.lock:
            results = run_beat_validator()
            caught = sum(result["decision"] == "DENY" for result in results)
            return {
                "reply": f"Beat the validator: caught {caught} of {len(results)}.",
                "executed": [],
                "refused": [],
                "results": results,
            }

    def clear_session_history(self) -> None:
        """Remove conversation history for the current session without touching seed data."""
        with self.lock:
            sid = SHOPPER["session_id"]
            db.execute("DELETE FROM turn_log WHERE thread_id = ?", (sid,))
            db.execute("DELETE FROM notes WHERE session_id = ?", (sid,))

    def reset(self) -> None:
        with self.lock:
            LOG.clear()
            db.init(reset=True)
            self.build()

    def swap_profile(self) -> str:
        with self.lock:
            now = "reference" if live_profile() == "student" else "student"
            os.environ["KESTREL_CONTROLS"] = now
            LOG.clear()
            self.build()
            return now


# -- request bodies ------------------------------------------------------------

class _ChatBody(BaseModel):
    message: str = ""


class _AttackBody(BaseModel):
    id: str = ""


# -- app factory ---------------------------------------------------------------

def create_app(narrow: bool = False) -> FastAPI:
    """Create and return the configured FastAPI application."""
    db.init()
    room = Room(narrow=narrow)

    app = FastAPI(title="Kestrel")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/state")
    def get_state() -> dict[str, Any]:
        s = snapshot(room.boundary)
        rows = db.query("SELECT name FROM customers WHERE id = ?",
                        (SHOPPER["customer_id"],))
        s["session"] = {
            "customer_id": SHOPPER["customer_id"],
            "name": rows[0]["name"] if rows else "Customer",
        }
        s["profile"] = live_profile()
        s["tools"] = len(REGISTRY.names())
        return s

    @app.get("/api/scenarios")
    def get_scenarios() -> dict[str, Any]:
        from ..attacks.scenarios import SCENARIOS

        items = [
            {"id": s.id, "title": s.title, "day": s.day,
             "entry": int(s.entry_surface)} for s in SCENARIOS
        ]
        beat = {"id": "beat_the_validator", "title": "Beat the validator",
                "day": 1, "entry": 1}
        # Insert immediately after indirect_injection_helpdoc
        idx = next(
            (i for i, s in enumerate(items) if s["id"] == "indirect_injection_helpdoc"),
            len(items) - 1,
        )
        items.insert(idx + 1, beat)
        return {"scenarios": items}

    @app.post("/api/chat")
    def post_chat(body: _ChatBody) -> dict[str, Any]:
        message = (body.message or "").strip()
        if not message:
            return {"error": "empty message"}
        return room.turn(message)

    @app.post("/api/attack")
    def post_attack(body: _AttackBody) -> dict[str, Any]:
        from ..attacks.scenarios import BY_ID

        sid = body.id
        if sid == "beat_the_validator":
            out = room.beat_validator()
            out["prompt"] = "Beat the validator"
            return out
        scenario = BY_ID.get(sid)
        if scenario is None:
            return {"error": "unknown scenario"}
        room.clear_session_history()
        LOG.clear()
        out = room.turn(scenario.prompt or scenario.narrative, scenario_id=scenario.id)
        out["prompt"] = scenario.prompt or f"[{scenario.id}]"
        return out

    @app.post("/api/reset")
    def post_reset() -> dict[str, Any]:
        room.reset()
        return {"ok": True}

    @app.post("/api/profile")
    def post_profile() -> dict[str, Any]:
        return {"profile": room.swap_profile()}

    return app


def serve(port: int | None = None, narrow: bool = False) -> None:
    """Start the FastAPI server with uvicorn (blocks). Used for standalone use."""
    import uvicorn

    app = create_app(narrow=narrow)
    port = port or CONFIG.console_port
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
