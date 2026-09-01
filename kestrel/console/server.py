"""The local web console: type at Kestrel, watch the control room react.

    python -m kestrel console          then open http://localhost:8899

Stdlib http.server. No FastAPI, no uvicorn, no npm, nothing to install on a lab
machine, and it starts in under a second.

Endpoints:

    GET  /                 the page
    GET  /api/state        zones, breaches, mediation, recent events
    GET  /api/scenarios    the attack corpus, for the dropdown
    POST /api/chat         {"message": "..."}  -> one turn
    POST /api/attack       {"id": "..."}       -> run a scenario
    POST /api/reset        clear the event log and reseed
    POST /api/profile      facilitator: swap student <-> reference controls
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .. import db
from ..boundary import ActionBoundary, Session
from ..config import CONFIG, reload as reload_config
from ..controls import profile as live_profile
from ..events import LOG
from ..tools.registry import REGISTRY
from .panel import snapshot
from .ui import PAGE

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


class _Handler(BaseHTTPRequestHandler):
    room: Room = None  # type: ignore[assignment]

    # -- plumbing ----------------------------------------------------------
    def _send(self, payload: Any, status: int = 200, html: bool = False) -> None:
        body = payload.encode() if html else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type",
                         "text/html; charset=utf-8" if html else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _body(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode() or "{}")
        except json.JSONDecodeError:
            return {}

    def log_message(self, *args: Any) -> None:
        pass  # the console is for the room, not for the terminal

    # -- routes ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/state"):
            state = snapshot(self.room.boundary)
            rows = db.query("SELECT name FROM customers WHERE id = ?",
                            (SHOPPER["customer_id"],))
            state["session"] = {
                "customer_id": SHOPPER["customer_id"],
                "name": rows[0]["name"] if rows else "Customer",
            }
            state["profile"] = live_profile()
            state["tools"] = len(REGISTRY.names())
            return self._send(state)

        if self.path.startswith("/api/scenarios"):
            from ..attacks.scenarios import SCENARIOS

            scenarios = [
                {"id": s.id, "title": s.title, "day": s.day,
                 "entry": int(s.entry_surface)} for s in SCENARIOS
            ]
            scenarios.append({"id": "beat_the_validator",
                              "title": "Beat the validator", "day": 1,
                              "entry": 1})
            return self._send({"scenarios": scenarios})

        return self._send(PAGE, html=True)

    def do_POST(self) -> None:  # noqa: N802
        body = self._body()

        if self.path.startswith("/api/chat"):
            message = (body.get("message") or "").strip()
            if not message:
                return self._send({"error": "empty message"}, 400)
            return self._send(self.room.turn(message))

        if self.path.startswith("/api/attack"):
            from ..attacks.scenarios import BY_ID

            scenario_id = body.get("id", "")
            if scenario_id == "beat_the_validator":
                out = self.room.beat_validator()
                out["prompt"] = "Beat the validator (8 payloads)"
                return self._send(out)
            scenario = BY_ID.get(scenario_id)
            if scenario is None:
                return self._send({"error": "unknown scenario"}, 404)
            out = self.room.turn(scenario.prompt or scenario.narrative,
                                 scenario_id=scenario.id)
            out["prompt"] = scenario.prompt or f"[{scenario.id}]"
            return self._send(out)

        if self.path.startswith("/api/reset"):
            self.room.reset()
            return self._send({"ok": True})

        if self.path.startswith("/api/profile"):
            return self._send({"profile": self.room.swap_profile()})

        return self._send({"error": "not found"}, 404)


def serve(boundary: Any = None, port: int | None = None,
          background: bool = False, narrow: bool = False) -> ThreadingHTTPServer:
    db.init()
    _Handler.room = Room(narrow=narrow)
    port = port or CONFIG.console_port
    httpd = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    if background:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd
    print(f"\n  Kestrel is on http://localhost:{port}")
    print("  Left: the customer's chat. Right: the control room.")
    print(f"  Controls: {live_profile()}   Tools: "
          f"{'narrow' if narrow else 'as shipped'}   (ctrl-c to stop)\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("  stopped.")
    return httpd
