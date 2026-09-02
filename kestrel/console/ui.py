"""Streamlit frontend for the Kestrel control room.

Left column: the customer's chat widget — white, friendly, what the customer sees.
Right column: the control room — dark, instrumented, what the facilitator sees.

Start via:
    python -m kestrel console

The API URL is injected by cmd_console via the KESTREL_API_URL environment variable.
"""

import html as _html
import os

import requests
import streamlit as st

API = os.environ.get("KESTREL_API_URL", "http://localhost:8899")

st.set_page_config(
    page_title="Kestrel",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 0.5rem; padding-bottom: 0; max-width: 100%; }

  /* chat bubbles */
  .bubble { max-width: 82%; padding: 11px 15px; border-radius: 16px;
            font-size: 15px; line-height: 1.5; white-space: pre-wrap;
            word-break: break-word; margin: 5px 0; }
  .from-user  { background: #003D7C; color: #fff;
                border-bottom-right-radius: 5px; margin-left: auto; }
  .from-agent { background: #fff; color: #16222E;
                border-bottom-left-radius: 5px;
                box-shadow: 0 1px 3px rgba(20,40,60,.14); }
  .from-agent.refused { border-left: 4px solid #59B6E8; }

  /* beat-validator payload/result bubbles */
  .payload-bubble { background: #003D7C; color: #E8F0F8;
                    font-family: monospace; font-size: 12px;
                    padding: 10px 14px; border-radius: 10px; margin: 5px 0;
                    word-break: break-all; white-space: pre-wrap; }
  .payload-id { font-size: 11px; opacity: .7; margin-bottom: 4px; }
  .validator-bubble { background: #fff; color: #16222E;
                      font-family: monospace; font-size: 13px; line-height: 1.5;
                      padding: 10px 14px; border-radius: 10px;
                      border-bottom-left-radius: 5px; margin: 5px 0; }
  .validator-bubble.denied  { border-left: 4px solid #E4573D; }
  .validator-bubble.allowed { border-left: 4px solid #5FD08A; }

  /* control room zones */
  .zone-row { display: flex; align-items: center; gap: 12px;
              padding: 12px 16px; margin-bottom: 6px; border-radius: 3px; }
  .zone-dot    { width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }
  .zone-name   { font-weight: 700; color: #E8F0F8; min-width: 190px; font-size: 14px; }
  .zone-status { font-weight: 700; letter-spacing: .05em; min-width: 160px; font-size: 13px; }
  .zone-why    { color: #93AEC7; font-size: 13px;
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* note boxes */
  .note-box { padding: 13px 17px; border-radius: 3px; margin: 8px 0;
              background: #11304F; border: 1px solid #1D4570;
              font-size: 14px; color: #93AEC7; }
  .note-box.ok  { border-color: #5FD08A; color: #5FD08A; }
  .note-box.bad { border-color: #E4573D; background: #2B1712;
                  color: #E4573D; font-weight: 700; }
  .note-head { letter-spacing: .1em; font-weight: 700;
               display: block; margin-bottom: 4px; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# ── helpers ────────────────────────────────────────────────────────────────────

def _get(path: str) -> dict:
    try:
        return requests.get(f"{API}{path}", timeout=5).json()
    except Exception:
        return {}


def _post(path: str, body: dict | None = None) -> dict:
    try:
        return requests.post(f"{API}{path}", json=body or {}, timeout=30).json()
    except Exception:
        return {}


def _esc(s: object) -> str:
    return _html.escape(str(s or ""))


def _visible(text: str) -> str:
    return "".join(
        f"\\x{ord(c):02x}" if (ord(c) < 32 or ord(c) == 127) else c
        for c in text
    )


# ── session state ──────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "scenarios" not in st.session_state:
    st.session_state.scenarios = _get("/api/scenarios").get("scenarios", [])
if "_state_stale" not in st.session_state:
    st.session_state._state_stale = True

# ── fetch state only when something changed ────────────────────────────────────
# Widget interactions (e.g. dropdown changes) rerun the script but should NOT
# hit the API — only actual user actions (Send, Run attack, Reset, Switch) do.

if st.session_state._state_stale:
    st.session_state._cached_state = _get("/api/state")
    st.session_state._state_stale = False

state = st.session_state._cached_state
scenarios = st.session_state.scenarios
session_info = state.get("session", {})

# ── layout ─────────────────────────────────────────────────────────────────────

left, right = st.columns([2, 3], gap="medium")

# ══════════════════════════════════════════════════════════════════════════════
# LEFT — customer chat widget
# ══════════════════════════════════════════════════════════════════════════════

with left:
    st.markdown(
        f'<div style="background:#003D7C;color:#fff;padding:14px 22px;'
        f'border-radius:6px 6px 0 0">'
        f'<div style="font-weight:700;font-size:17px">Kestrel Support</div>'
        f'<div style="font-size:13px;opacity:.85">Signed in as '
        f'{_esc(session_info.get("name",""))} &middot; '
        f'customer {_esc(session_info.get("customer_id",""))}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Build chat log HTML
    bubbles = []
    if not st.session_state.messages:
        bubbles.append(
            '<div style="color:#6B7C8C;font-size:14px;text-align:center;'
            'padding:26px 10px;line-height:1.6">'
            'Hi! How can I help today?<br>'
            '<b>Try: Can you show me my recent orders?</b></div>'
        )
    for msg in st.session_state.messages:
        kind = msg.get("kind", "normal")
        if kind == "payload":
            bubbles.append(
                f'<div class="payload-bubble">'
                f'<div class="payload-id">[{_esc(msg["id"])}]</div>'
                f'{_esc(_visible(msg["text"]))}</div>'
            )
        elif kind == "validator":
            cls = "denied" if msg.get("refused") else "allowed"
            bubbles.append(
                f'<div class="validator-bubble {cls}">{_esc(msg["text"])}</div>'
            )
            if msg.get("response"):
                bubbles.append(
                    f'<div class="bubble from-agent">{_esc(msg["response"])}</div>'
                )
        elif msg["role"] == "user":
            bubbles.append(
                f'<div style="text-align:right">'
                f'<div class="bubble from-user">{_esc(msg["content"])}</div></div>'
            )
        else:
            cls = "from-agent refused" if msg.get("refused") else "from-agent"
            bubbles.append(
                f'<div class="bubble {cls}">{_esc(msg["content"])}</div>'
            )

    st.markdown(
        '<div style="background:#EEF2F6;border:1px solid #DCE4EC;'
        'border-top:none;border-radius:0 0 0 0;padding:16px;'
        'min-height:440px;max-height:520px;overflow-y:auto">'
        + "".join(bubbles) + "</div>",
        unsafe_allow_html=True,
    )

    # Composer
    with st.form("chat_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns([5, 1])
        with c1:
            prompt = st.text_input(
                "msg", placeholder="Type a message…", label_visibility="collapsed"
            )
        with c2:
            send = st.form_submit_button("Send", use_container_width=True)

    if send and prompt.strip():
        text = prompt.strip()
        st.session_state.messages.append({"role": "user", "content": text})
        with st.spinner("Kestrel is thinking…"):
            d = _post("/api/chat", {"message": text})
        st.session_state.messages.append({
            "role": "assistant",
            "content": d.get("reply", "The agent is not reachable. Check the terminal."),
            "refused": bool(d.get("refused")),
        })
        st.session_state._state_stale = True
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — control room
# ══════════════════════════════════════════════════════════════════════════════

with right:
    st.markdown(
        '<h2 style="color:#E8F0F8;letter-spacing:.12em;margin-bottom:2px">'
        'KESTREL CONTROL ROOM</h2>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"{state.get('count', 0)} security events · "
        "four control zones over eight surfaces · "
        f"{state.get('tools', 0)} tools"
    )

    # Controls bar
    scenario_map = {s["id"]: f"day {s['day']} — {s['title']}" for s in scenarios}
    b1, b2, b3, b4, b5 = st.columns([3, 1, 1, 1, 1])

    with b1:
        selected = st.selectbox(
            "scenario",
            options=[s["id"] for s in scenarios],
            format_func=lambda x: scenario_map.get(x, x),
            label_visibility="collapsed",
        )
    with b2:
        run_clicked = st.button("Run attack", type="primary", use_container_width=True)
    with b3:
        reset_clicked = st.button("Reset", use_container_width=True)
    with b4:
        st.markdown(
            f'<div style="font-size:13px;color:#93AEC7;padding-top:8px">'
            f'controls: <b style="color:#E8F0F8">'
            f'{_esc(state.get("profile", "student"))}</b></div>',
            unsafe_allow_html=True,
        )
    with b5:
        swap_clicked = st.button("Switch", use_container_width=True)

    if run_clicked and selected:
        with st.spinner("Running attack…"):
            d = _post("/api/attack", {"id": selected})
        st.session_state.messages = []          # fresh panel for each attack
        prompt_txt = d.get("prompt") or f"[{selected}]"
        st.session_state.messages.append({"role": "user", "content": prompt_txt})
        st.session_state.messages.append({
            "role": "assistant",
            "content": d.get("reply", ""),
            "refused": bool(d.get("refused")),
        })
        for result in d.get("results") or []:
            st.session_state.messages.append(
                {"kind": "payload", "id": result["id"], "text": result["text"]}
            )
            classifier = f" ({result['classifier']})" if result.get("classifier") else ""
            st.session_state.messages.append({
                "kind": "validator",
                "text": (f"{result['layer']} → {result['decision']}"
                         f"{classifier}\n{result['note']}"),
                "refused": result["decision"] == "DENY",
                "response": result.get("response", ""),
            })
        st.session_state._state_stale = True
        st.rerun()

    if reset_clicked:
        _post("/api/reset")
        st.session_state.messages = []
        st.session_state._state_stale = True
        st.rerun()

    if swap_clicked:
        _post("/api/profile")
        st.session_state._state_stale = True
        st.rerun()

    # ── zones ─────────────────────────────────────────────────────────────────

    ZONE_COLORS = {
        "clear": "#5FD08A", "green": "#5FD08A",
        "refused": "#59B6E8",
        "amber": "#F5811F",
        "dark": "#5C7893",
    }
    ZONE_LABELS = {
        "clear": "CLEAR", "green": "CLEAR",
        "refused": "REFUSED",
        "amber": "AWAITING APPROVAL",
        "dark": "NOT WIRED",
    }

    zones_html = []
    for z in state.get("zones", []):
        status = z.get("status", "dark")
        color = ZONE_COLORS.get(status, "#5C7893")
        label = ZONE_LABELS.get(status, "NOT WIRED")
        zones_html.append(
            f'<div class="zone-row" style="background:#11304F;border-left:5px solid {color}">'
            f'<div class="zone-dot" style="background:{color}"></div>'
            f'<div class="zone-name">{_esc(z.get("name", ""))}</div>'
            f'<div class="zone-status" style="color:{color}">{label}</div>'
            f'<div class="zone-why">{_esc(z.get("last", ""))}</div>'
            f'</div>'
        )
    st.markdown("".join(zones_html), unsafe_allow_html=True)

    # ── data boundary breach ───────────────────────────────────────────────────

    breaches = state.get("breaches", [])
    if breaches:
        who = sorted({
            c for b in breaches
            for c in (b.get("detail") or {}).get("customers_in_result", [])
        })
        st.markdown(
            f'<div class="note-box bad">'
            f'<span class="note-head">DATA BOUNDARY — BREACHED</span>'
            f"Another customer's data left the tool "
            f'(customer {_esc(", ".join(str(w) for w in who))}).'
            f'No control refused it — this line comes from a detector.</div>',
            unsafe_allow_html=True,
        )

    # ── mediation invariant ────────────────────────────────────────────────────

    med = state.get("mediation") or {}
    total = med.get("total_invocations", 0)
    if not total:
        st.markdown(
            '<div class="note-box">Mediation invariant: nothing has run yet.</div>',
            unsafe_allow_html=True,
        )
    elif med.get("holds"):
        st.markdown(
            f'<div class="note-box ok">'
            f'<span class="note-head">MEDIATION HOLDS</span>'
            f'{total} tool calls, every one through the boundary.</div>',
            unsafe_allow_html=True,
        )
    else:
        bad_tools = sorted({u["tool"] for u in med.get("unmediated", [])})
        st.markdown(
            f'<div class="note-box bad">'
            f'<span class="note-head">MEDIATION BROKEN</span>'
            f'{len(med["unmediated"])} of {total} tool calls bypassed the boundary: '
            f'{_esc(", ".join(bad_tools))}</div>',
            unsafe_allow_html=True,
        )

    # ── events table ──────────────────────────────────────────────────────────

    DECISION_COLORS = {
        "deny": "#59B6E8", "breach": "#E4573D",
        "hold": "#F5811F", "allow": "#93AEC7",
    }
    TH = ("border-bottom:1px solid #1D4570;color:#93AEC7;font-weight:600;"
          "font-size:12px;letter-spacing:.04em;text-align:left;padding:0 10px 7px 0")
    TD = "border-bottom:1px solid #1a3a5c;padding:5px 10px 5px 0;color:#E8F0F8"
    MONO = f"{TD};font-family:monospace;font-size:12px"

    events = list(reversed(state.get("events", [])))
    if events:
        rows = [
            f'<table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:6px">'
            f'<thead><tr>'
            f'<th style="{TH}">Surface</th>'
            f'<th style="{TH}">Control</th>'
            f'<th style="{TH}">Decision</th>'
            f'<th style="{TH}">Reason</th>'
            f'<th style="{TH}">Tool</th>'
            f'</tr></thead><tbody>'
        ]
        for e in events:
            dec = (e.get("decision") or "").lower()
            dc = DECISION_COLORS.get(dec, "#93AEC7")
            rows.append(
                f'<tr>'
                f'<td style="{TD}">{_esc(e.get("surface", ""))}</td>'
                f'<td style="{MONO}">{_esc(e.get("control", ""))}</td>'
                f'<td style="{TD};color:{dc};font-weight:700">{_esc(dec.upper())}</td>'
                f'<td style="{TD}">{_esc(e.get("reason", ""))}</td>'
                f'<td style="{MONO}">{_esc(e.get("tool", "") or "")}</td>'
                f'</tr>'
            )
        rows.append("</tbody></table>")
        st.markdown("".join(rows), unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="color:#93AEC7;padding:24px 0;text-align:center">'
            "Send a message, or run an attack.</div>",
            unsafe_allow_html=True,
        )
