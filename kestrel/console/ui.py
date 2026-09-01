"""The classroom UI: a chat widget beside a control room.

The split is the teaching device, so the two halves are deliberately dressed
differently. Left is what the customer sees: white, rounded, friendly, the
"clean, familiar, unthreatening" widget from slide 8. Right is what you see:
dark, dense, instrumented. Same request, two truths.

No webfonts, no CDN, no build step. Lab networks have an allowlist and this
page has to render on one.
"""

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Kestrel</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{
    --navy:#003D7C; --orange:#F5811F;
    --field:#0B2038; --panel:#11304F; --line:#1D4570;
    --ink:#E8F0F8; --muted:#93AEC7;
    --clear:#5FD08A; --refused:#59B6E8; --breach:#E4573D; --hold:#F5811F;
    --off:#5C7893;
    --shop:#FFFFFF; --shopbg:#EEF2F6; --shopink:#16222E; --shopmuted:#6B7C8C;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
    --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{margin:0;font-family:var(--sans);background:var(--field);color:var(--ink);
       display:grid;grid-template-columns:minmax(380px,42%) 1fr;height:100vh;
       overflow:hidden;font-size:16px}
  @media (max-width:900px){body{grid-template-columns:1fr;overflow:auto;height:auto}}

  /* ---------- left: the storefront widget ---------- */
  .shop{background:var(--shopbg);color:var(--shopink);display:flex;
        flex-direction:column;height:100vh;border-right:1px solid var(--line)}
  @media (max-width:900px){.shop{height:auto;min-height:70vh}}
  .shop header{background:var(--navy);color:#fff;padding:16px 22px}
  .shop header .name{font-weight:700;font-size:17px}
  .shop header .who{font-size:13px;opacity:.85;margin-top:3px}
  .log{flex:1;overflow-y:auto;padding:20px 22px;display:flex;
       flex-direction:column;gap:14px}
  .bubble{max-width:82%;padding:12px 16px;border-radius:16px;font-size:16px;
          line-height:1.5;white-space:pre-wrap;word-break:break-word}
  .from-user{align-self:flex-end;background:var(--navy);color:#fff;
             border-bottom-right-radius:5px}
  .from-agent{align-self:flex-start;background:var(--shop);color:var(--shopink);
              border-bottom-left-radius:5px;box-shadow:0 1px 3px rgba(20,40,60,.14)}
  .from-agent.refused{border-left:4px solid var(--refused)}
  .payload{align-self:stretch;max-width:100%;word-break:break-all;
           font-family:var(--mono);font-size:13px}
  .payload-id{font-size:11px;opacity:.7;margin-bottom:4px}
  .validator-result{font-size:14px;line-height:1.45}
  .hint{color:var(--shopmuted);font-size:14px;text-align:center;padding:26px 10px;
        line-height:1.6}
  .composer{border-top:1px solid #DCE4EC;background:var(--shop);padding:14px 16px;
            display:flex;gap:10px}
  .composer input{flex:1;border:1px solid #C7D3DF;border-radius:22px;
                  padding:12px 18px;font:inherit;color:var(--shopink);outline:none}
  .composer input:focus{border-color:var(--navy);box-shadow:0 0 0 3px rgba(0,61,124,.15)}
  .composer button{background:var(--navy);color:#fff;border:0;border-radius:22px;
                   padding:12px 22px;font:inherit;font-weight:600;cursor:pointer}
  .composer button:disabled{opacity:.5;cursor:default}

  /* ---------- right: the control room ---------- */
  .room{padding:22px 26px;overflow-y:auto;height:100vh}
  @media (max-width:900px){.room{height:auto}}
  h1{font-size:17px;letter-spacing:.14em;margin:0 0 3px;font-weight:700}
  .sub{color:var(--muted);font-size:13px;margin-bottom:18px}
  .bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px;align-items:center}
  select,.btn{background:var(--panel);color:var(--ink);border:1px solid var(--line);
              border-radius:4px;padding:8px 12px;font:inherit;font-size:14px;
              cursor:pointer}
  .btn:hover,select:hover{border-color:var(--muted)}
  .btn.go{background:var(--orange);border-color:var(--orange);color:#231202;
          font-weight:700}
  .profile{margin-left:auto;font-size:13px;color:var(--muted)}
  .profile b{color:var(--ink)}

  .zone{display:grid;grid-template-columns:12px 210px 175px 1fr;gap:16px;
        align-items:center;padding:14px 18px;margin-bottom:8px;background:var(--panel);
        border-left:5px solid var(--line);border-radius:3px}
  .zone .dot{width:11px;height:11px;border-radius:50%;background:var(--off)}
  .zone .name{font-weight:700;font-size:15px}
  .zone .status{font-size:13.5px;font-weight:700;letter-spacing:.05em;color:var(--off)}
  .zone .why{color:var(--muted);font-size:13.5px;overflow:hidden;
             text-overflow:ellipsis;white-space:nowrap}
  .zone.clear{border-left-color:var(--clear)}
  .zone.clear .dot{background:var(--clear)} .zone.clear .status{color:var(--clear)}
  .zone.refused{border-left-color:var(--refused)}
  .zone.refused .dot{background:var(--refused)}
  .zone.refused .status{color:var(--refused)}
  .zone.hold{border-left-color:var(--hold)}
  .zone.hold .dot{background:var(--hold)} .zone.hold .status{color:var(--hold)}

  .note{margin:16px 0;padding:14px 18px;border-radius:3px;background:var(--panel);
        border:1px solid var(--line);font-size:14.5px;color:var(--muted)}
  .note.ok{border-color:var(--clear);color:var(--clear)}
  .note.bad{border-color:var(--breach);background:#2B1712;color:var(--breach);
            font-weight:700}
  .note .head{letter-spacing:.1em;font-weight:700;display:block;margin-bottom:4px}

  table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
  th{text-align:left;color:var(--muted);font-weight:600;padding:0 10px 7px 0;
     border-bottom:1px solid var(--line);font-size:12px;letter-spacing:.04em}
  td{padding:6px 10px 6px 0;border-bottom:1px solid rgba(29,69,112,.45);
     vertical-align:top}
  td.deny{color:var(--refused);font-weight:700}
  td.hold{color:var(--hold);font-weight:700}
  td.breach{color:var(--breach);font-weight:700}
  td.allow{color:var(--muted)}
  td.mono{font-family:var(--mono);font-size:12.5px}
  .empty{color:var(--muted);padding:26px 0;text-align:center}
</style>

<section class="shop">
  <header>
    <div class="name">Kestrel Support</div>
    <div class="who" id="who">signed in</div>
  </header>
  <div class="log" id="log">
    <div class="hint">Hi! How can I help today?<br>
      Try: <b>Can you show me my recent orders?</b></div>
  </div>
  <div class="composer">
    <input id="msg" placeholder="Type a message…" autocomplete="off">
    <button class="btn" id="send">Send</button>
  </div>
</section>

<section class="room">
  <h1>KESTREL CONTROL ROOM</h1>
  <div class="sub" id="sub">no security events yet</div>

  <div class="bar">
    <select id="scenario"></select>
    <button class="btn go" id="run">Run attack</button>
    <button class="btn" id="reset">Reset</button>
    <span class="profile">controls: <b id="profile">student</b></span>
    <button class="btn" id="swap">Switch</button>
  </div>

  <div id="zones"></div>
  <div class="note" id="breach" hidden></div>
  <div class="note" id="inv">Mediation invariant: nothing has run yet.</div>

  <table>
    <thead><tr><th>Surface</th><th>Control</th><th>Decision</th><th>Reason</th>
      <th>Tool</th></tr></thead>
    <tbody id="rows"><tr><td colspan="5" class="empty">
      Send a message, or run an attack.</td></tr></tbody>
  </table>
</section>

<script>
const CLS = {clear:'clear', refused:'refused', amber:'hold', dark:'', green:'clear'};
const LBL = {clear:'CLEAR', refused:'REFUSED', amber:'AWAITING APPROVAL',
             dark:'NOT WIRED', green:'CLEAR'};
const $ = id => document.getElementById(id);
let busy = false;

function esc(s){ const d=document.createElement('div'); d.textContent=s??''; 
  return d.innerHTML; }

function say(who, text, refused, extraClass=''){
  const hint = $('log').querySelector('.hint');
  if (hint) hint.remove();
  const b = document.createElement('div');
  b.className = 'bubble ' + (who==='user'?'from-user':'from-agent') +
                (refused?' refused':'') + (extraClass?' '+extraClass:'');
  b.textContent = text;
  $('log').appendChild(b);
  $('log').scrollTop = $('log').scrollHeight;
}

function visiblePayload(text){
  return [...text].map(char => {
    const code = char.charCodeAt(0);
    return code < 32 || code === 127 ? '\\\\x' + code.toString(16).padStart(2, '0') : char;
  }).join('');
}

async function post(path, body){
  const r = await fetch(path, {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(body||{})});
  return r.json();
}

async function send(){
  const box = $('msg'); const text = box.value.trim();
  if (!text || busy) return;
  busy = true; $('send').disabled = true;
  say('user', text); box.value = '';
  try {
    const d = await post('/api/chat', {message:text});
    say('agent', d.reply, (d.refused||[]).length > 0);
  } catch(e){ say('agent', 'The agent is not reachable. Check the terminal.'); }
  busy = false; $('send').disabled = false; box.focus();
  refresh();
}

async function runAttack(){
  if (busy) return;
  busy = true; $('run').disabled = true;
  const id = $('scenario').value;
  const d = await post('/api/attack', {id});
  say('user', d.prompt || ('[' + id + ']'));
  say('agent', d.reply, (d.refused||[]).length > 0);
  if (d.results) {
    d.results.forEach(result => {
      const hint = $('log').querySelector('.hint');
      if (hint) hint.remove();
      const b = document.createElement('div');
      b.className = 'bubble from-user payload';
      const label = document.createElement('div');
      label.className = 'payload-id';
      label.textContent = '[' + result.id + ']';
      const body = document.createElement('div');
      body.textContent = visiblePayload(result.text);
      b.appendChild(label);
      b.appendChild(body);
      $('log').appendChild(b);
      $('log').scrollTop = $('log').scrollHeight;
      const classifier = result.classifier ? ' (' + result.classifier + ')' : '';
      say('agent', result.layer + ' -> ' + result.decision + classifier + '\\n' + result.note,
          result.decision === 'DENY', 'validator-result');
      if (result.response) {
        say('agent', result.response, false);
      }
    });
  }
  busy = false; $('run').disabled = false;
  refresh();
}

async function refresh(){
  let d;
  try { d = await (await fetch('/api/state')).json(); } catch(e){ return; }

  $('who').textContent = 'Signed in as ' + d.session.name +
    ' \\u00b7 customer ' + d.session.customer_id;
  $('profile').textContent = d.profile;
  $('sub').textContent = d.count + ' security events \\u00b7 ' +
    'four control zones over eight surfaces \\u00b7 ' + d.tools + ' tools';

  $('zones').innerHTML = d.zones.map(z => `
    <div class="zone ${CLS[z.status]||''}">
      <div class="dot"></div><div class="name">${esc(z.name)}</div>
      <div class="status">${LBL[z.status]||''}</div>
      <div class="why">${esc(z.last)}</div>
    </div>`).join('');

  const br = $('breach');
  if (d.breaches && d.breaches.length){
    const who = [...new Set(d.breaches.flatMap(b =>
      (b.detail && b.detail.customers_in_result) || []))].join(', ');
    br.hidden = false; br.className = 'note bad';
    br.innerHTML = '<span class="head">DATA BOUNDARY \\u2014 BREACHED</span>' +
      'Another customer\\'s data left the tool (customer ' + esc(who) +
      '). No control refused it \\u2014 this line comes from a detector.';
  } else { br.hidden = true; }

  const inv = $('inv');
  if (!d.mediation || !d.mediation.total_invocations){
    inv.className = 'note'; inv.textContent = 'Mediation invariant: nothing has run yet.';
  } else if (d.mediation.holds){
    inv.className = 'note ok';
    inv.innerHTML = '<span class="head">MEDIATION HOLDS</span>' +
      d.mediation.total_invocations + ' tool calls, every one through the boundary.';
  } else {
    const t = [...new Set(d.mediation.unmediated.map(u => u.tool))].join(', ');
    inv.className = 'note bad';
    inv.innerHTML = '<span class="head">MEDIATION BROKEN</span>' +
      d.mediation.unmediated.length + ' of ' + d.mediation.total_invocations +
      ' tool calls bypassed the boundary: ' + esc(t);
  }

  const rows = d.events.slice().reverse();
  $('rows').innerHTML = rows.length ? rows.map(e => `
    <tr><td>${e.surface}</td><td class="mono">${esc(e.control)}</td>
        <td class="${e.decision}">${e.decision.toUpperCase()}</td>
        <td>${esc(e.reason)}</td><td class="mono">${esc(e.tool||'')}</td></tr>`
  ).join('') : '<tr><td colspan="5" class="empty">Send a message, or run an attack.</td></tr>';
}

async function boot(){
  const s = await (await fetch('/api/scenarios')).json();
  $('scenario').innerHTML = s.scenarios.map(x =>
    `<option value="${x.id}">day ${x.day} \\u2014 ${esc(x.title)}</option>`).join('');
  refresh();
}

$('send').onclick = send;
$('msg').onkeydown = e => { if (e.key === 'Enter') send(); };
$('run').onclick = runAttack;
$('reset').onclick = async () => { await post('/api/reset'); $('log').innerHTML =
  '<div class="hint">Reset. Hi! How can I help today?</div>'; refresh(); };
$('swap').onclick = async () => { await post('/api/profile'); refresh(); };
boot();
setInterval(refresh, 2000);
</script>
"""
