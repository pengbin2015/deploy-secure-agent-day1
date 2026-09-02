"""Kestrel's turn, as named nodes.

These are the boxes on the Block 0 diagram, one function each:

    read_message  ->  retrieve  ->  recall  ->  consult_helpers
                                                     |
                                                   plan            (the model)
                                                     |
                                          route: act, or reply?
                                             /              \\
                                          act             reply
                                       (boundary)

These are the graph's nodes. ``graph.py`` wires them; the wiring holds nothing
security-relevant, because every control attaches to a node or to the boundary
between two of them.

Two conventions worth noticing, because both are security decisions:

  * ``state`` is checkpointed and therefore attacker-influenceable. It holds
    text and plain data only.
  * the session, the boundary and the model live in ``config["configurable"]``
    and are never checkpointed. Identity is not conversation state, and nothing
    the model writes can reach it.
"""

# NOTE: no `from __future__ import annotations` here. LangGraph inspects these
# node signatures when the graph is built and needs the real RunnableConfig
# type, not a postponed string.

import contextvars
from typing import Any, Optional, TypedDict

try:  # LangGraph inspects node signatures and wants its own config type
    from langchain_core.runnables import RunnableConfig
except ImportError:  # pragma: no cover
    RunnableConfig = dict  # type: ignore[misc,assignment]

from .. import db
from ..boundary import ToolRequest
from ..console.detectors import check_data_boundary
from ..surfaces import Surface
from .llm import ToolCall

class KestrelState(TypedDict, total=False):
    """What is checkpointed, and therefore what an attacker can influence.

    Text and plain data only. The session is not here on purpose — see
    ``runtime_scope`` below.
    """

    message: str
    scenario_id: Optional[str]
    turn_id: str
    context: list[str]
    proposed: list[dict[str, Any]]
    executed: list[dict[str, Any]]
    refused: list[dict[str, Any]]
    approvals: dict[str, bool]
    tool_calls_this_turn: int
    reply: str


State = KestrelState


#: The runtime objects for the turn in flight: the session, the agent, the
#: boundary. A context variable rather than graph state, because LangGraph
#: checkpoints state and identity must never be checkpointed, replayed or
#: rewritten by anything the model produced.
_RUNTIME: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "kestrel_runtime", default={}
)


class runtime_scope:
    """Bind the session and agent for one turn, under either runtime."""

    def __init__(self, **objects: Any) -> None:
        self.objects = objects
        self._reset = None

    def __enter__(self) -> dict:
        self._reset = _RUNTIME.set(self.objects)
        return self.objects

    def __exit__(self, *exc: Any) -> None:
        if self._reset is not None:
            _RUNTIME.reset(self._reset)


def rt(config: Optional[RunnableConfig] = None) -> Any:
    """The runtime objects. Deliberately not part of the graph state."""
    objects = _RUNTIME.get()
    if objects:
        return objects
    return (config or {}).get("configurable", {})


def _kw(state: State, config: Optional[RunnableConfig]) -> dict[str, Any]:
    session = rt(config)["session"]
    return {
        "turn_id": state["turn_id"],
        "session_id": session.session_id,
        "scenario_id": state.get("scenario_id"),
    }


# -- nodes ------------------------------------------------------------------

def read_message(state: State, config: Optional[RunnableConfig] = None) -> State:
    """Surface 1. The user's message, screened before it reaches the model."""
    agent = rt(config)["agent"]
    item = agent.zones.screen(
        agent.zones.Intake(state["message"], int(Surface.USER_MESSAGE)),
        **_kw(state, config),
    )
    return {"context": state["context"] + [f"[user/{item.label}] {item.text}"]}


def retrieve(state: State, config: Optional[RunnableConfig] = None) -> State:
    """Surface 2. Help-centre content. Retrieved, not typed — and not trusted."""
    agent = rt(config)["agent"]
    words = [w for w in state["message"].lower().split() if len(w) > 4]
    rows = db.query("SELECT title, body FROM help_docs")
    hits = [f"{r['title']}: {r['body']}" for r in rows
            if any(w in r["body"].lower() for w in words)][:2]
    ctx = list(state["context"])
    for doc in hits:
        item = agent.zones.screen(
            agent.zones.Intake(doc, int(Surface.RETRIEVED_CONTENT)),
            **_kw(state, config),
        )
        ctx.append(f"[retrieved/{item.label}] {item.text}")
    return {"context": ctx}


def recall(state: State, config: Optional[RunnableConfig] = None) -> State:
    """Surface 7. Anything the agent decided to remember from earlier."""
    import json
    from .memory import history as _turn_history

    agent = rt(config)["agent"]
    session = rt(config)["session"]
    ctx = list(state["context"])

    # Recent conversation turns so the agent knows what has already been said.
    for row in _turn_history(session.session_id)[-4:]:
        try:
            data = json.loads(row["blob"])
            user_msg = (data.get("message") or "")[:300]
            agent_reply = (data.get("reply") or "")[:400]
            if user_msg:
                ctx.append(f"[memory/turn] user: {user_msg} | agent: {agent_reply}")
        except Exception:
            pass

    # Agent-decided structured memories (Day 2 workshop — Surface 7 security control).
    for note in agent.zones.recall(session.session_id):
        ctx.append(f"[memory/{note['kind']}] {note['body']}")
    return {"context": ctx}


def consult_helpers(state: State, config: Optional[RunnableConfig] = None) -> State:
    """Surface 6. Two helper agents. Internal, and therefore easy to trust."""
    agent = rt(config)["agent"]
    session = rt(config)["session"]
    kw = _kw(state, config)
    ctx = list(state["context"])

    policy = agent.helpers["lookup_policy"](state["message"])
    policy = agent.zones.screen_agent_output("lookup_policy", policy, **kw)
    ctx.append(f"[helper/policy] {policy}")

    summary = agent.helpers["summarise_orders"](
        session.customer_id, session=session, boundary=agent.boundary
    )
    summary = agent.zones.screen_agent_output("summarise_orders", summary, **kw)
    ctx.append(f"[helper/orders] {summary}")
    return {"context": ctx}


def plan(state: State, config: Optional[RunnableConfig] = None) -> State:
    """Surface 8. The model proposes actions. It does not take them."""
    agent = rt(config)["agent"]
    session = rt(config)["session"]
    calls = agent.model.plan(state["message"], session=session,
                             context=state.get("context", []),
                             scenario_id=state.get("scenario_id"))
    return {"proposed": [{"tool": c.tool, "args": dict(c.args)} for c in calls]}


def route(state: State, config: Optional[RunnableConfig] = None) -> str:
    """The model decides the route — the conditional edge on the diagram.

    Which is exactly why the next node is a boundary and not a tool.
    """
    return "act" if state.get("proposed") else "reply"


def act(state: State, config: Optional[RunnableConfig] = None) -> State:
    """Surface 3. Every proposal crosses the ActionBoundary. No exceptions."""
    agent = rt(config)["agent"]
    session = rt(config)["session"]
    kw = _kw(state, config)

    ctx_checks: dict[str, Any] = {
        "approvals": state.get("approvals", {}),
        "tool_calls_this_turn": state.get("tool_calls_this_turn", 0),
    }
    executed = list(state.get("executed", []))
    refused = list(state.get("refused", []))
    context = list(state["context"])

    for call in state.get("proposed", []):
        request = ToolRequest(call["tool"], dict(call["args"]),
                              origin_surface=int(Surface.THE_MODEL),
                              scenario_id=state.get("scenario_id"))
        outcome = agent.boundary.execute(request, session,
                                         turn_id=state["turn_id"], ctx=ctx_checks)
        ctx_checks["tool_calls_this_turn"] += 1
        if outcome.allowed:
            # Observed, not prevented: did someone else's data just leave?
            check_data_boundary(call["tool"], outcome.result, session,
                                turn_id=state["turn_id"],
                                scenario_id=state.get("scenario_id"))
            # Surface 4. What comes back is untrusted too.
            screened = agent.zones.screen_tool_result(call["tool"], outcome.result, **kw)
            executed.append({"tool": call["tool"], "args": request.args,
                             "result": screened})
            context.append(f"[tool/{call['tool']}] {screened}")
        else:
            denial = outcome.denial
            refused.append({
                "tool": call["tool"],
                "args": request.args,
                "control": denial.control if denial else "tool_execution",
                "reason": outcome.error,
            })
    return {"executed": executed, "refused": refused, "context": context,
            "tool_calls_this_turn": ctx_checks["tool_calls_this_turn"]}


def _money(cents: Any) -> str:
    try:
        return f"${int(cents) / 100:,.2f}"
    except (TypeError, ValueError):
        return str(cents)


def _render(result: Any) -> str:
    """Put tool results into the transcript the way the widget would show them.

    This matters for the anchor: a reply that says "Done — list_my_orders" hides
    the breach. The room has to see the name, the address and the laptop.
    """
    rows = result if isinstance(result, list) else [result]
    out = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(str(row))
            continue
        if "item" in row:
            line = f"#{row.get('id')} · {row.get('item')} · {_money(row.get('total_cents'))}"
            if row.get("status"):
                line += f" · {row['status']}"
            if row.get("customer_name"):
                line += f"\n    {row['customer_name']} — {row.get('ship_to', '')}"
            out.append(line)
        else:
            out.append(", ".join(f"{k}: {v}" for k, v in row.items()
                                 if k not in ("untrusted",)))
    return "\n".join(out) if out else "(nothing found)"


def reply(state: State, config: Optional[RunnableConfig] = None) -> State:
    agent = rt(config)["agent"]
    if state.get("refused"):
        r = state["refused"][0]
        text = (f"I can't do that. The {r['control']} control refused "
                f"{r['tool']}: {r['reason']}.")
    elif state.get("executed"):
        parts = ["Here's what I found:"]
        for e in state["executed"]:
            parts.append(_render(e["result"]))
        text = "\n".join(parts)
    else:
        text = agent.model.say(state["message"], "\n".join(state["context"]))
    return {"reply": text}


#: The linear spine of the graph. `route` puts the branch after `plan`.
SEQUENCE = [
    ("read_message", read_message),
    ("retrieve", retrieve),
    ("recall", recall),
    ("consult_helpers", consult_helpers),
    ("plan", plan),
    ("act", act),
    ("reply", reply),
]

NODE_SURFACES = {
    "read_message": Surface.USER_MESSAGE,
    "retrieve": Surface.RETRIEVED_CONTENT,
    "recall": Surface.STATE_MEMORY,
    "consult_helpers": Surface.OTHER_AGENTS,
    "plan": Surface.THE_MODEL,
    "act": Surface.TOOL_ARGUMENTS,
    "reply": None,
}


def new_state(message: str, scenario_id: Optional[str], turn_id: str,
              approvals: Optional[dict] = None) -> State:
    return {
        "message": message,
        "scenario_id": scenario_id,
        "turn_id": turn_id,
        "context": [],
        "proposed": [],
        "executed": [],
        "refused": [],
        "approvals": approvals or {},
        "tool_calls_this_turn": 0,
        "reply": "",
    }
