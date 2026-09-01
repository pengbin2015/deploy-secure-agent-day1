"""Kestrel command line.

    python -m kestrel doctor              check this machine before class
    python -m kestrel seed [--reset]      create the database
    python -m kestrel chat "..."          one turn against the agent
    python -m kestrel attack <id>         run one scenario end to end
    python -m kestrel beat-validator      run the Block 2 intake exercise
    python -m kestrel list                the attack corpus
    python -m kestrel evidence a|b|c|all  the three kinds of proof
    python -m kestrel board [--day N]     the Attack Board
    python -m kestrel console             the control room, on a port
    python -m kestrel graph               the node/edge structure
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from . import db
from .boundary import ActionBoundary, Session
from .config import CONFIG
from .console import board as board_mod
from .console.panel import render
from .events import LOG
from .tools.registry import REGISTRY


def _load_tools(narrow: bool = False) -> None:
    """Kestrel ships wide. Teams narrow it in Workshop 1, Phase B."""
    if narrow:
        from .tools import narrow as mod
    else:
        from .tools import wide as mod
    REGISTRY.replace_all(list(mod.SPECS))


def _session(customer_id: int = 1001, roles: tuple[str, ...] = ("customer",)) -> Session:
    return Session(session_id="cli", customer_id=customer_id, roles=roles)


# -- commands ---------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []

    v = sys.version_info
    checks.append(("python >= 3.10", v >= (3, 10), f"{v.major}.{v.minor}.{v.micro}"))

    try:
        db.init(reset=False)
        n = len(db.query("SELECT id FROM orders"))
        checks.append(("database", n > 0, f"{n} seeded orders at {CONFIG.db_path}"))
    except Exception as exc:
        checks.append(("database", False, str(exc)))

    try:
        _load_tools()
        checks.append(("tools", True, f"{len(REGISTRY.names())} registered"))
    except Exception as exc:
        checks.append(("tools", False, str(exc)))

    try:
        import langgraph  # noqa: F401
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: F401

        from .agent.graph import build

        build(checkpoint=False)
        checks.append(("langgraph graph compiles", True,
                       f"{len(list(__import__('kestrel.agent.nodes', fromlist=['x']).SEQUENCE))} nodes"))
    except Exception as exc:
        checks.append(("langgraph graph compiles", False,
                       f"{exc} — pip install -r requirements.txt"))

    try:
        from .evidence import evidence_b
        from .attacks.scenarios import get
        r = evidence_b(get("cross_tenant_order_leak"))
        checks.append(("scenario runs end to end", True, r.summary))
    except Exception as exc:
        checks.append(("scenario runs end to end", False, str(exc)))

    if CONFIG.llm == "gateway":
        ok, msg = _probe(CONFIG.llm_base_url)
        checks.append(("llm gateway reachable", ok, msg))
    else:
        checks.append(("model", True, "scripted (offline, no key needed)"))

    if CONFIG.langfuse_enabled:
        ok, msg = _probe(CONFIG.langfuse_host)
        checks.append(("langfuse reachable", ok, msg))
    else:
        checks.append(("langfuse", True, "not configured (optional)"))

    width = max(len(n) for n, _, _ in checks)
    print()
    for name, ok, detail in checks:
        print(f"  {'ok  ' if ok else 'FAIL'}  {name.ljust(width)}   {detail}")
    failed = [n for n, ok, _ in checks if not ok]
    print()
    if failed:
        print(f"  {len(failed)} check(s) failed: {', '.join(failed)}")
        print("  See docs/SETUP.md — most failures here are proxy or egress.")
        return 1
    print("  Ready.")
    return 0


def _probe(url: str) -> tuple[bool, str]:
    import urllib.error
    import urllib.request

    if not url:
        return False, "no URL configured"
    try:
        urllib.request.urlopen(url, timeout=5)
        return True, url
    except urllib.error.HTTPError as exc:
        return True, f"{url} (HTTP {exc.code} — reachable)"
    except Exception as exc:
        return False, f"{url} — {exc}"


def cmd_seed(args: argparse.Namespace) -> int:
    db.init(reset=args.reset)
    print(f"database ready at {CONFIG.db_path}"
          f"{' (reset)' if args.reset else ''}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .attacks.scenarios import SCENARIOS

    for s in SCENARIOS:
        print(f"  day {s.day}  {s.id:<28} {s.title}")
        print(f"           enters at surface {int(s.entry_surface)}, "
              f"expected stop: {s.expected_control} "
              f"(surface {int(s.expected_control_surface)})")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    from .agent.graph import Kestrel

    db.init()
    _load_tools(args.narrow)
    agent = Kestrel()
    turn = agent.handle(args.message, _session())
    print(f"\n  kestrel> {turn.reply}\n")
    print(render(turn.events, mediation=agent.boundary.mediation_report()))
    return 0


def cmd_attack(args: argparse.Namespace) -> int:
    from .agent.graph import Kestrel
    from .attacks.scenarios import get

    db.init()
    _load_tools(args.narrow)
    scenario = get(args.scenario)
    agent = Kestrel()
    print(f"\n  {scenario.title}")
    print(f"  {scenario.narrative}\n")
    if scenario.prompt:
        print(f"  attacker> {scenario.prompt}")
    turn = agent.handle(scenario.prompt or scenario.narrative,
                        scenario.make_session(), scenario_id=scenario.id)
    print(f"  kestrel > {turn.reply}\n")
    print(render(turn.events, mediation=agent.boundary.mediation_report()))
    return 0


def run_beat_validator() -> list[dict[str, str]]:
    """Run all Block 2 payloads through the active intake controls."""
    from .attacks.payloads import PAYLOADS
    from .controls.intake import Intake
    from .controls import load_zone_controls
    from .events import ALLOW as _ALLOW
    from .surfaces import Surface

    zones = load_zone_controls()

    _LAYER = {
        "oversize_input": "structural",
        "control_characters": "structural",
        "injection_shape_in_user_message": "content",
        "semantic_intent_flagged": "semantic",
        "semantic_layer_unavailable": "semantic unavailable",
    }
    _CLASSIFIER = {
        "semantic_intent_flagged": "gateway: SUSPICIOUS",
        "clean": "gateway: CLEAR",
        "semantic_layer_unavailable": "gateway: unavailable",
    }
    _NOTE = {
        "oversize_input":                  "Caught: message exceeds the character limit.",
        "control_characters":              "Caught: control character detected — parsers may disagree on where the message ends.",
        "injection_shape_in_user_message": "Caught: recognised injection pattern in user message.",
        "semantic_intent_flagged":         "Caught: semantic classifier flagged suspicious intent.",
        "semantic_layer_unavailable":      "Missed: semantic layer not configured — intent was not checked.",
        "clean":                           "Missed: semantic layer found nothing wrong — ownership was not verified.",
        "flagged_untrusted_content":       "Flagged: injection shape in retrieved content, passed with provenance mark.",
    }

    results = []
    for payload in PAYLOADS:
        item = zones.screen(Intake(payload.text, int(Surface.USER_MESSAGE)),
                    scenario_id="beat_the_validator")
        event = LOG.all()[-1]

        response = ""
        if event.decision == _ALLOW and payload.tool:
            from .tools import narrow as _tools
            from .events import SecurityEvent as _SecurityEvent
            fn = getattr(_tools, payload.tool, None)
            if fn:
                try:
                    result = fn(**dict(payload.tool_args))
                    response = (
                        f"Order {result['order_id']} is being shipped to "
                        f"{result['ship_to']} ({result['customer_name']})."
                    )
                except Exception:
                    pass
            LOG.pop()  # replace input_validation:clean with the meaningful tool event
            LOG.emit(_SecurityEvent(
                surface=int(Surface.TOOL_ARGUMENTS),
                control="scope_resources",
                decision=_ALLOW,
                reason="ownership_not_verified",
                tool=payload.tool,
                scenario_id="beat_the_validator",
            ))

        results.append({
            "id": payload.id,
            "text": payload.text,
            "layer": _LAYER.get(event.reason, "passed all layers"),
            "decision": event.decision.upper(),
            "note": _NOTE.get(event.reason, event.reason),
            "classifier": _CLASSIFIER.get(event.reason, ""),
            "response": response,
        })
    return results


def cmd_beat_validator(args: argparse.Namespace) -> int:
    LOG.clear()
    results = run_beat_validator()
    caught = sum(result["decision"] == "DENY" for result in results)
    print()
    for result in results:
        text = result["text"].replace("\n", " ")
        print(f"  {text[:72]:<72} {result['layer']:<20} {result['decision']}")
        if result.get("response"):
            print(f"    -> {result['response']}")
    print(f"\n  caught {caught} of {len(results)}.")
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    from .agent.graph import Kestrel
    from .attacks.scenarios import SCENARIOS, for_day
    from .evidence import evidence_a, evidence_b, evidence_c

    db.init()
    _load_tools(args.narrow)
    kind = args.kind.lower()
    scenarios = for_day(args.day) if args.day else SCENARIOS
    boundary = ActionBoundary()
    REGISTRY.reset_invocations()
    results = []

    if kind in ("a", "all"):
        from .agent.llm import get_model
        model = get_model()
        results += [evidence_a(s, model) for s in scenarios]
    if kind in ("b", "all"):
        results += [evidence_b(s, boundary) for s in scenarios]
    if kind in ("c", "all"):
        # exercise a real turn so helper paths get a chance to misbehave
        agent = Kestrel(boundary=boundary)
        for s in scenarios[:1]:
            agent.handle(s.prompt or s.narrative, s.make_session(), scenario_id=s.id)
        results.append(evidence_c(boundary))

    print()
    for r in results:
        print(f"  {r.status:<9} {r.kind}  {r.scenario_id:<28} {r.summary}")
    hard = [r for r in results if not r.advisory]
    failed = [r for r in hard if not r.passed]
    print()
    print(f"  {len(hard) - len(failed)}/{len(hard)} deterministic checks passed.")
    if any(r.advisory for r in results):
        print("  Evidence A is observed, never asserted on: the model declining "
              "today proves nothing about tomorrow.")
    return 1 if failed else 0


def cmd_board(args: argparse.Namespace) -> int:
    from .attacks.scenarios import SCENARIOS, for_day
    from .evidence import evidence_b

    db.init()
    _load_tools(args.narrow)
    boundary = ActionBoundary()
    for s in (for_day(args.day) if args.day else SCENARIOS):
        evidence_b(s, boundary)
    print()
    print(board_mod.to_markdown(args.day) if args.markdown
          else board_mod.to_text(args.day))
    print()
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Show the turn structure. Works with or without LangGraph installed."""
    from .agent import graph as graph_mod
    from .agent import nodes

    print()
    print("  Kestrel's turn — nodes, and the surface each one touches")
    print("  " + "-" * 58)
    for name, _ in nodes.SEQUENCE:
        surface = nodes.NODE_SURFACES.get(name)
        label = f"surface {int(surface)}" if surface else "-"
        arrow = "  |" if name != "reply" else ""
        print(f"  {name:<20} {label}")
        if name == "plan":
            print("  " + " " * 20 + "conditional edge: the model decides the route")
        if arrow:
            print(arrow)
    print()
    print("  Whatever the model chooses, the only path to a tool is `act`,")
    print("  and `act` is the ActionBoundary.")
    print()
    if args.mermaid:
        print(graph_mod.mermaid())
    return 0


def cmd_console(args: argparse.Namespace) -> int:
    from .console.server import serve

    db.init()
    serve(port=args.port, narrow=args.narrow)
    return 0


# -- wiring -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kestrel", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--narrow", action="store_true",
                   help="load the narrow tool set instead of the wide one")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)

    s = sub.add_parser("seed")
    s.add_argument("--reset", action="store_true")
    s.set_defaults(fn=cmd_seed)

    sub.add_parser("list").set_defaults(fn=cmd_list)

    s = sub.add_parser("chat")
    s.add_argument("message")
    s.set_defaults(fn=cmd_chat)

    s = sub.add_parser("attack")
    s.add_argument("scenario")
    s.set_defaults(fn=cmd_attack)

    sub.add_parser("beat-validator").set_defaults(fn=cmd_beat_validator)

    s = sub.add_parser("evidence")
    s.add_argument("kind", choices=["a", "b", "c", "all"])
    s.add_argument("--day", type=int)
    s.set_defaults(fn=cmd_evidence)

    s = sub.add_parser("board")
    s.add_argument("--day", type=int)
    s.add_argument("--markdown", action="store_true")
    s.set_defaults(fn=cmd_board)

    s = sub.add_parser("graph")
    s.add_argument("--mermaid", action="store_true")
    s.set_defaults(fn=cmd_graph)

    s = sub.add_parser("console")
    s.add_argument("--port", type=int, default=CONFIG.console_port)
    s.set_defaults(fn=cmd_console)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
