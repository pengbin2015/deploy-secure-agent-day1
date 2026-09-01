# Workshop 1 — Constrain Kestrel's reach

**Day 1, 2:25pm–5:15pm.** Teams of three to four, one machine per team.

By the end, the three attacks you ran this morning fail on your build, and you
can prove it in a way that does not depend on what the model happened to say.

---

## Phase A — Make the attacks fail on input (≈30 min)

Implement `kestrel/controls/intake.py`.

Three layers, cheapest first: structural, content, semantic. Allowlist beats
denylist — describe the shape you accept, not every shape you fear.

```
python -m kestrel attack direct_injection_refund
python -m kestrel --narrow evidence b --day 1
```

Then answer the question the slide asks, in one sentence in your commit
message: **which of this morning's attacks does intake validation not stop, and
why?** If your answer is "none", you have not run
`indirect_injection_helpdoc` yet.

Intake is a cost-raiser and a signal generator. It is not a wall. The rest of
the afternoon is what happens after it fails.

---

## Phase B — Narrow the tools (≈40 min)

Open `kestrel/tools/wide.py`. Three anti-patterns, all live:

| Tool | Shape |
|---|---|
| `lookup_orders(sql)` | free-form query string — a blank cheque |
| `account_action(action, target_id, value)` | one tool, four behaviours |
| `fetch_and_refund(order_id)` | reads untrusted content **and** takes a side effect |

Replace them with narrow, typed tools. `kestrel/tools/narrow.py` shows the
target shape; do not just import it, work out why each parameter is bounded the
way it is.

The test is not "is this validated". It is **can the malicious call still be
written down**. `get_order(order_id: int)` has no grammar for "somebody else's
order".

This is where beginners slow first. If you are stuck at 3:30, take
`narrow.py` and spend your time on Phase C instead.

---

## Phase C — Enforce authority below the model (≈40 min)

Implement, in this order:

1. `authorize_identity` — may this caller use this verb at all?
2. `scope_resources` — does this particular row belong to this caller?
3. `business_rules` — rules that hold regardless of who is asking

Decide everything against `session`, never against anything the model believes
or the user claims. The agent receives an identity; it never establishes one.

Then fix the other thing. Run:

```
python -m kestrel --narrow evidence c
```

It fails. Something is calling a tool without going through the boundary. Find
it, and fix it properly rather than by deleting the call.

---

## Phase D — Attack swap (≈25 min)

Pull another team's branch and run your attacks against their build. Do not run
against their machine over the network — conference wifi will quietly break it,
and reading their code is the better exercise anyway.

```
git fetch origin
git switch --detach origin/team-<n>-day1
python -m kestrel --narrow evidence all
```

Write down one thing they did that you did not.

Fast finishers: this is your phase. If you finish it, you are released.

---

## Phase E — Prove and ship (≈15 min)

Three kinds of evidence, and only two of them count.

**A — adversarial.** Steer the live model toward the dangerous action. Report
what happened. Never assert on it: the model declining today proves nothing
about tomorrow.

**B — control.** Hand the dangerous request straight to the boundary. Assert
that it is denied, by the expected control, at the expected surface. A denial
for the wrong reason is a coincidence.

**C — mediation.** No tool executes without a matching SecurityEvent. B can
pass on every case while a helper calls a tool directly, and this is the only
test that sees it.

```
python -m unittest discover -s tests -v
python -m kestrel --narrow board --markdown
```

Then ship it, because Day 2 starts from what you push:

```
git add -A
git commit -m "day 1: intake, narrow tools, authority below the model"
git push origin HEAD:team-<n>-day1
```

**Done when:** every Day 1 row on the Attack Board is green, Evidence B passes
for the right control at the right surface, Evidence C holds, and your branch
is on the remote.
