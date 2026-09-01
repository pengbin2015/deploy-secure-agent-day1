"""Kestrel as a LangGraph agent.

This is the box labelled KESTREL AGENT · LangGraph on the map, in code:

    read_message -> retrieve -> recall -> consult_helpers -> plan
                                                              |
                                                    (conditional edge)
                                                         /         \\
                                                      act -------> reply -> END

The three primitives from the framework slide are all here and all visible:

    state              a TypedDict, checkpointed to SQLite
    nodes              the functions in nodes.py
    conditional edges  route(), where the model chooses what happens next

`act` is the ActionBoundary. Whatever the model routes to, that is the only
edge that reaches a tool.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from ..boundary import ActionBoundary, Session
from ..config import CONFIG
from ..controls import load_zone_controls
from ..events import LOG, new_turn_id
from . import load_helpers, nodes
from .llm import ToolCall, get_model
from .memory import save_checkpoint


@dataclass
class Turn:
    """Everything that happened in one exchange. This is what the console reads."""

    turn_id: str
    session: Session
    message: str
    scenario_id: str | None = None
    context: list[str] = field(default_factory=list)
    proposed: list[ToolCall] = field(default_factory=list)
    executed: list[dict[str, Any]] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)
    reply: str = ""

    @property
    def events(self):
        return LOG.for_turn(self.turn_id)


def build(checkpoint: bool = True) -> Any:
    """Compile Kestrel's graph."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "LangGraph is not installed.\n"
            "  pip install -r requirements.txt\n"
            "Then: python -m kestrel doctor"
        ) from exc

    graph = StateGraph(nodes.KestrelState)
    for node_name, fn in nodes.SEQUENCE:
        graph.add_node(node_name, fn)

    graph.add_edge(START, "read_message")
    graph.add_edge("read_message", "retrieve")
    graph.add_edge("retrieve", "recall")
    graph.add_edge("recall", "consult_helpers")
    graph.add_edge("consult_helpers", "plan")

    # The model decides the route. This is the edge the course is about: an
    # attacker can influence the choice, so the destination has to be a
    # boundary rather than a tool.
    graph.add_conditional_edges("plan", nodes.route,
                                {"act": "act", "reply": "reply"})
    graph.add_edge("act", "reply")
    graph.add_edge("reply", END)

    saver = None
    if checkpoint:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            conn = sqlite3.connect(CONFIG.db_path, check_same_thread=False)
            saver = SqliteSaver(conn)
            saver.setup()
        except Exception:
            saver = None  # checkpointing is a convenience, never a control
    return graph.compile(checkpointer=saver)


def mermaid() -> str:
    return build(checkpoint=False).get_graph().draw_mermaid()


class Kestrel:
    def __init__(self, boundary: ActionBoundary | None = None,
                 model: Any = None) -> None:
        self.boundary = boundary or ActionBoundary()
        self.model = model or get_model()
        self.zones = load_zone_controls()
        self.helpers = load_helpers()
        self.app = build()

    def handle(self, message: str, session: Session, *,
               scenario_id: str | None = None,
               approvals: dict[str, bool] | None = None) -> Turn:
        turn_id = new_turn_id()
        state = nodes.new_state(message, scenario_id, turn_id, approvals)
        config = {"configurable": {"thread_id": session.session_id}}

        # The session and the agent are bound here, outside the graph state,
        # so nothing that gets checkpointed can reach them.
        with nodes.runtime_scope(session=session, agent=self,
                                 thread_id=session.session_id):
            state = self.app.invoke(state, config)

        turn = Turn(turn_id, session, message, scenario_id)
        turn.context = state.get("context", [])
        turn.proposed = [ToolCall(c["tool"], c["args"])
                         for c in state.get("proposed", [])]
        turn.executed = state.get("executed", [])
        turn.refused = state.get("refused", [])
        turn.reply = state.get("reply", "")

        save_checkpoint(session.session_id, {
            "turn_id": turn_id,
            "message": message,
            "executed": [e["tool"] for e in turn.executed],
            "refused": [r["tool"] for r in turn.refused],
        })
        return turn
