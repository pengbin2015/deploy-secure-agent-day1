# Workshop 2 — Contain the interior

**Day 2, 4:05pm–5:15pm.** Same teams, same machines, starting from the branch
you pushed yesterday.

Yesterday you secured the edge. This morning someone walked past all of it,
because the payload did not arrive as input.

```
git switch team-<n>-day1
python -m kestrel --narrow evidence all
```

Everything from Day 1 should still be green. Now the interior.

---

## Phase A — Quarantine what comes back (≈20 min)

Implement `screen_tool_result` and `screen_agent_output` in
`kestrel/controls/results.py`.

A tool result is not data you wrote. It is a payload from whoever last touched
that row, that API or that other agent. Neutralise rather than drop: the
customer's gift note is still their data and the agent still has to be able to
quote it back to them.

```
python -m kestrel --narrow evidence b --day 2
```

Targets: `tool_result_injection`, `external_api_payload`,
`helper_agent_inheritance`.

A helper's answer is a claim, not an instruction, and it must not widen what
the main agent may do. Trust does not travel up a call chain because the caller
is yours.

---

## Phase B — Decide what sticks (≈20 min)

Implement `propose_note` in `kestrel/controls/state.py`. This is where teams
slow down, so leave time.

The Day 1 rule, applied to memory: **the model may propose a memory; code and
humans decide what sticks.**

| Kind | What it is | Who decides |
|---|---|---|
| `preference` | the user set it themselves | allowed |
| `procedural` | how the agent does things | human approval |
| `policy` | what the agent is allowed to do | human approval |

Refuse anything whose origin surface is untrusted. The `origin_surface` and
`trusted` columns already exist in the schema — that they were never populated
is the bug.

A poisoned memory outlives the conversation that caused it. That is what makes
surface 7 the worst one.

---

## Phase C — Gate and limit (≈20 min)

`require_approval` in `approval.py`, using **your team's own answers** from
yesterday's "who may say yes" activity — not a list from the slides.

Return `Decision.hold`, not `Decision.deny`. The request is not wrong; it is
not yours alone to make. And it fires before the action, not as a summary
afterwards.

Then `apply_limits` in `limits.py`. Cap tool calls per turn and refund value
per session. Every call in `runaway_refund_loop` is authorised, in scope and
within policy — the damage is in the repetition. The goal is not prevention. It
is that the worst case is a bill you survive and an alert you can act on.

---

## Phase D — Prove it (≈10 min)

```
python -m unittest discover -s tests -v
python -m kestrel --narrow evidence all
python -m kestrel --narrow board --markdown
```

Ten scenarios, both days, every one denied by the expected control at the
expected surface, and the mediation invariant holding across the lot.

```
git commit -am "day 2: quarantine, memory policy, approval gates, limits"
git push origin HEAD:team-<n>-day2
```

**Done when:** the whole board is green, and you can say out loud which of the
eight surfaces each control attaches to and why it is not somewhere else.
