# Architecture

One rule decided what got built here:

> Every piece of custom Kestrel code must exist because it teaches something.

Tracing is Langfuse. Orchestration is whatever you like. Deployment is a Python
process. What is written here is the security model, the evidence, and the
teaching console — because those three things are what the course is about.

## The map, and the four places software intervenes

```
                       UNTRUSTED CONTENT
                              |
  surfaces 1, 2  ------> INTAKE CONTROLS        raise cost, produce signal
                              |
                            MODEL   (surface 8)
                              |
                      proposes an action
                              |
  surface 3      ------> ACTION BOUNDARY        the deterministic chokepoint
                              |
                            TOOL
                              |
  surfaces 4, 5, 6, 7 --> RESULT / STATE CONTROLS
                              |
                        MODEL / USER

  across all eight  ---> OBSERVE + VERIFY       SecurityEvents, traces, tests
```

These four zones do not replace the eight-surface map. They say where we
enforce on it. Intake sits before the model; the boundary sits between the
model and the tool; result and state controls sit after. Collapsing them into
one box would teach a wall, and the wall is what the course argues against.

## Why the ActionBoundary is special

The model is probabilistic. The boundary is not. Any model-driven action has to
cross this one object before it becomes a real-world effect, which makes it the
only place where you can make a promise instead of an estimate.

Six checks, in the order they are taught:

1. `validate_arguments` — Block 3
2. `authorize_identity` — Block 4
3. `scope_resources` — Block 4
4. `business_rules` — Block 4
5. `require_approval` — Day 2, Block 9
6. `apply_limits` — Day 2, Block 10

Checks 2 and 3 are adjacent because they are the two that failed in the anchor
breach: the caller was authenticated, and the resource was never checked.

Not in the boundary: `execute`, and result validation. The boundary permits;
the tool executes. If execution lived inside the boundary, the boundary would
just be the tool runtime. Result validation is surface 4, and it is a different
zone.

## Two guarantees

**Every boundary decision emits a SecurityEvent — allow or deny.** Denied
attempts are evidence too, and they are what turns the console red.

**No tool can execute without a matching SecurityEvent.** This is the one worth
testing, and it is the difference between an architecture you intend and an
architecture you have.

The mechanism is small. The boundary sets a token in a context variable before
invoking; the registry records the token with the invocation. Anything that
calls a tool from somewhere else records `token=None`.

```
boundary sets token ---> registry.invoke ---> Invocation(token=abc123)
helper calls directly -> registry.invoke ---> Invocation(token=None)   <- caught
```

`kestrel/agent/helpers.py` contains exactly that bug, on purpose.

## The graph

The seven turn stages are functions in `kestrel/agent/nodes.py`; `graph.py`
wires them into a LangGraph `StateGraph`:

```
read_message -> retrieve -> recall -> consult_helpers -> plan
                                                          |
                                                (conditional edge)
                                                     /         \
                                                  act -------> reply -> END
```

- **state** — a `TypedDict`, checkpointed to SQLite by `SqliteSaver`
- **nodes** — the functions in `nodes.py`
- **conditional edges** — `route()`, where the model chooses what happens next

One runtime, on purpose. The deck labels Kestrel a LangGraph agent on the
diagram it reuses at the top of every block, and the framework slide's transfer
point is made by a comparison table in the room, not by the repo shipping two
implementations of itself. Two runners would give teams a way to fix a control
and have it behave differently in the path they were not testing.

### What is not in the state

The session. State is checkpointed, replayed and influenced by whatever reached
surfaces 1, 2, 4, 6 and 7. Identity lives in a runtime scope that is never
serialised, so no amount of state manipulation can change who the caller is.

This is also why Kestrel's own per-turn snapshot table is called `turn_log`:
`checkpoints` belongs to LangGraph's `SqliteSaver`, and the two must not
collide.

## SecurityEvent

Not a log line. A statement about which engineering guarantee held.

```python
SecurityEvent(
    surface=3,                                # where the control was exercised
    control="scope_resources",
    decision="deny",
    reason="resource_not_owned_by_session",
    tool="get_order",
    session_id="sess-...",
    scenario_id="cross_tenant_order_leak",
)
```

`surface` is the enforcement point, not the entry point. An attack arrives at
surface 1 and is stopped at surface 3; the scenario records the first, the
event records the second. Joining them is what builds the Attack Board.

Two consumers, deliberately separate. Langfuse answers *what happened in this
run*. The control room answers *which guarantee held* — the only question a
beginner can act on in the first hour.

## The Attack Board is half automatic, on purpose

Kestrel rows are generated from SecurityEvents and maintain themselves. The
My Agent rows are participants reasoning about their own systems and have
nothing behind them. Automating those would delete the part of the course that
transfers.

## What is deliberately absent

- No LangSmith Deployment. LangGraph OSS plus a Python process is enough, and
  it keeps the security story vendor-neutral.
- No Postgres. SQLite carries every scenario in the course, including the
  Day 2 checkpoint and memory work.
- No container. One dependency, pre-installed in the lab image.
- No secrets in the repo. Keys arrive per team, on the day, in `.env`.
