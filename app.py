from __future__ import annotations

from uuid import uuid4

import streamlit as st

from game_state import SharedGameStore

st.set_page_config(
    page_title="킥앤런 디지털 작전판",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# Cache-bust token: bump this whenever SharedGameStore's interface changes.
# Streamlit Community Cloud can preserve a cached resource across a hot deploy,
# so a new app.py can otherwise keep an instance created from an older class.
STORE_CACHE_VERSION = "v4.1-controller-lease"


@st.cache_resource(show_spinner=False)
def get_store(cache_version: str) -> SharedGameStore:
    # cache_version is intentionally unused inside the function.  It is part of
    # the cache key so a deployment that changes the store schema creates a new
    # SharedGameStore instance instead of reusing an old cached object.
    _ = cache_version
    return SharedGameStore()


STORE = get_store(STORE_CACHE_VERSION)

# Defensive recovery for a stale resource left behind by an older deployment.
# If the imported class has the v4 controller API but the cached instance does
# not, clear only this function's cache and recreate the store immediately.
if not hasattr(STORE, "is_controller") and hasattr(SharedGameStore, "is_controller"):
    get_store.clear()
    STORE = get_store(STORE_CACHE_VERSION)

# If game_state.py itself was not replaced on GitHub, fail with an actionable
# message instead of an AttributeError deep inside the UI.
_REQUIRED_STORE_METHODS = (
    "is_controller",
    "claim_controller",
    "touch_controller",
    "release_controller",
    "controller_status",
)
_missing_store_methods = [name for name in _REQUIRED_STORE_METHODS if not hasattr(STORE, name)]
if _missing_store_methods:
    st.error(
        "game_state.py가 v4 파일로 갱신되지 않았습니다. "
        "GitHub의 app.py와 game_state.py를 둘 다 v4.1 파일로 교체한 뒤 앱을 Reboot 해주세요. "
        f"누락된 기능: {', '.join(_missing_store_methods)}"
    )
    st.stop()

BOARD_HTML = r"""
<div class="kr-shell">
  <div class="kr-header">
    <div>
      <div id="roomTitle" class="kr-title">킥앤런 작전판</div>
      <div class="kr-subtitle">선수와 공을 손가락으로 끌어서 배치하세요.</div>
    </div>
    <div id="syncBadge" class="kr-sync">● LIVE</div>
  </div>

  <div class="kr-main">
    <aside class="kr-toolbar">
      <section class="kr-tool-group">
        <div class="kr-tool-label">인원 설정</div>
        <div class="kr-counter team-a-soft">
          <strong>A팀</strong>
          <div class="kr-counter-controls">
            <button data-count-team="A" data-delta="-1" aria-label="A팀 한 명 줄이기">−</button>
            <span id="countA">0</span>
            <button data-count-team="A" data-delta="1" aria-label="A팀 한 명 늘리기">＋</button>
          </div>
        </div>
        <div class="kr-counter team-b-soft">
          <strong>B팀</strong>
          <div class="kr-counter-controls">
            <button data-count-team="B" data-delta="-1" aria-label="B팀 한 명 줄이기">−</button>
            <span id="countB">0</span>
            <button data-count-team="B" data-delta="1" aria-label="B팀 한 명 늘리기">＋</button>
          </div>
        </div>
      </section>

      <section class="kr-tool-group">
        <div class="kr-tool-label">공격팀 선택</div>
        <button class="kr-offense" data-offense="A">🔵 A팀 공격</button>
        <button class="kr-offense" data-offense="B">🔴 B팀 공격</button>
        <div class="kr-help">공격팀을 바꾸면 키커 1명만 홈에 남고, 나머지는 공격 대기석으로 이동합니다.</div>
      </section>

      <section class="kr-tool-group kr-actions">
        <div class="kr-tool-label">도구</div>
        <button id="ballHome">⚽ 공 원위치</button>
        <button id="resetBoard">↺ 배치 초기화</button>
      </section>
    </aside>

    <div class="kr-board-area">
      <div class="kr-play-area">
        <div id="field" class="kr-field">
          <div class="safe-zone">
            <div class="safe-title">안전지대 <small>최대 3명</small></div>
            <div class="safe-slots" aria-hidden="true"><i></i><i></i><i></i></div>
          </div>
          <div class="restriction-line"><span>수비제한선</span></div>
          <div class="home-mark"><span>HOME</span></div>
          <div id="playersLayer" class="players-layer"></div>
          <div id="ball" class="ball" role="img" aria-label="공">⚽</div>
        </div>

        <aside class="kr-bench">
          <div class="bench-heading">
            <strong id="benchTeam">공격 대기</strong>
            <span>WAITING</span>
          </div>
          <div class="kicker-card">
            <span>현재 키커</span>
            <strong id="currentKickerLabel">1번</strong>
          </div>
          <div id="benchPlayers" class="bench-players"></div>
          <button id="nextKicker" class="next-kicker">다음 키커 ▶</button>
          <div id="safeCount" class="safe-count">안전지대 0 / 3</div>
          <div class="bench-help">키커가 공을 찬 뒤 위치를 옮기고 <b>다음 키커</b>를 누르세요.</div>
        </aside>
      </div>

      <div class="kr-footer">
        <span><i class="legend-dot team-a"></i>A팀</span>
        <span><i class="legend-dot team-b"></i>B팀</span>
        <span id="modeText">편집 가능</span>
      </div>
    </div>
  </div>
</div>
"""

BOARD_CSS = r"""
.kr-shell {
  width:100%; height:100%; box-sizing:border-box; max-width:1040px; margin:0 auto;
  font-family:var(--st-font,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif);
  color:#1f2937; background:#f8fafc; border:1px solid #dbe4ee;
  border-radius:18px; padding:14px; overflow:hidden;
}
.kr-header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
.kr-title { font-size:22px; font-weight:800; letter-spacing:-0.02em; }
.kr-subtitle { font-size:13px; color:#64748b; margin-top:2px; }
.kr-sync { font-size:12px; font-weight:800; color:#15803d; background:#dcfce7; border-radius:999px; padding:6px 10px; white-space:nowrap; }
.kr-main { display:grid; grid-template-columns:190px minmax(0,740px); gap:14px; align-items:start; justify-content:center; }
.kr-toolbar { display:flex; flex-direction:column; gap:10px; min-width:0; }
.kr-tool-group { display:flex; flex-direction:column; align-items:stretch; gap:7px; background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:10px; }
.kr-tool-label { font-size:12px; font-weight:800; color:#64748b; margin-bottom:1px; }
.kr-counter { display:flex; align-items:center; justify-content:space-between; gap:7px; border-radius:10px; padding:7px 8px; font-size:13px; }
.kr-counter-controls { display:flex; align-items:center; gap:6px; }
.team-a-soft { background:#eff6ff; }
.team-b-soft { background:#fff1f2; }
.kr-counter button, .kr-tool-group > button, .next-kicker { border:1px solid #cbd5e1; background:#fff; border-radius:9px; min-width:34px; height:38px; padding:0 9px; font-size:13px; font-weight:800; cursor:pointer; }
.kr-counter button { min-width:31px; width:31px; height:31px; padding:0; font-size:18px; }
.kr-counter-controls span { min-width:20px; text-align:center; font-weight:800; }
.kr-counter button:disabled, .kr-toolbar button:disabled, .next-kicker:disabled { opacity:.45; cursor:not-allowed; }
.kr-offense { width:100%; }
.kr-offense.active { outline:3px solid rgba(15,118,110,.17); border-color:#0f766e !important; background:#f0fdfa !important; }
.kr-help { font-size:11px; line-height:1.45; color:#64748b; background:#f8fafc; border-radius:8px; padding:7px 8px; }
.kr-board-area { min-width:0; }
.kr-play-area { display:grid; grid-template-columns:minmax(0,1fr) 118px; gap:10px; align-items:stretch; }
.kr-field { position:relative; width:100%; height:640px; border-radius:16px; overflow:hidden; background:linear-gradient(180deg,#ecfccb 0%,#dcfce7 100%); border:3px solid #ffffff; box-shadow:inset 0 0 0 1px #a7c7a8; touch-action:none; user-select:none; }
.kr-field::before { content:""; position:absolute; left:9%; right:9%; top:23%; bottom:8%; border:2px solid rgba(255,255,255,.95); border-radius:36% 36% 10% 10%; pointer-events:none; }
.safe-zone { position:absolute; left:16%; right:16%; top:4%; height:16%; border:3px solid #eab308; background:rgba(254,240,138,.78); border-radius:16px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; color:#854d0e; box-shadow:0 2px 8px rgba(0,0,0,.08); pointer-events:none; }
.safe-title { font-weight:900; font-size:15px; }
.safe-title small { font-size:10px; font-weight:800; opacity:.75; margin-left:4px; }
.safe-slots { display:flex; gap:28px; }
.safe-slots i { width:30px; height:30px; border-radius:50%; border:2px dashed rgba(161,98,7,.45); background:rgba(255,255,255,.28); }
.restriction-line { position:absolute; left:5%; right:5%; top:63%; border-top:4px dashed rgba(185,28,28,.75); text-align:center; pointer-events:none; }
.restriction-line span { position:relative; top:-14px; display:inline-block; background:rgba(255,255,255,.86); color:#991b1b; padding:3px 8px; border-radius:999px; font-size:12px; font-weight:800; }
.home-mark { position:absolute; left:50%; bottom:3.5%; transform:translateX(-50%); width:78px; height:46px; background:#fff; border:3px solid #475569; clip-path:polygon(0 0,100% 0,88% 72%,50% 100%,12% 72%); display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:900; color:#334155; pointer-events:none; }
.players-layer { position:absolute; inset:0; pointer-events:none; }
.player { position:absolute; transform:translate(-50%,-50%); width:46px; height:46px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:900; font-size:17px; border:3px solid #fff; box-shadow:0 3px 10px rgba(15,23,42,.25); pointer-events:auto; touch-action:none; cursor:grab; z-index:5; }
.player:active, .ball:active { cursor:grabbing; transform:translate(-50%,-50%) scale(1.08); }
.player.team-a, .bench-player.team-a { background:#2563eb; }
.player.team-b, .bench-player.team-b { background:#e11d48; }
.player.offense { box-shadow:0 0 0 4px rgba(255,255,255,.9),0 0 0 8px rgba(15,118,110,.45),0 4px 12px rgba(15,23,42,.25); }
.player.current-kicker::before { content:"K"; position:absolute; left:-7px; top:-8px; width:19px; height:19px; border-radius:50%; background:#0f766e; color:#fff; display:flex; align-items:center; justify-content:center; font-size:10px; border:2px solid #fff; }
.player.own::after { content:""; position:absolute; width:8px; height:8px; border-radius:50%; background:#fde047; top:-5px; right:-3px; border:2px solid #fff; }
.ball { position:absolute; transform:translate(-50%,-50%); width:48px; height:48px; display:flex; align-items:center; justify-content:center; font-size:38px; filter:drop-shadow(0 3px 4px rgba(0,0,0,.25)); z-index:10; touch-action:none; cursor:grab; }
.kr-bench { height:640px; box-sizing:border-box; background:#fff; border:1px solid #dbe4ee; border-radius:14px; padding:9px; display:flex; flex-direction:column; gap:8px; overflow:hidden; }
.bench-heading { text-align:center; background:#f8fafc; border-radius:10px; padding:8px 4px; line-height:1.1; }
.bench-heading strong { display:block; font-size:12px; }
.bench-heading span { display:block; margin-top:4px; font-size:9px; color:#94a3b8; font-weight:800; letter-spacing:.08em; }
.kicker-card { background:#f0fdfa; border:1px solid #99f6e4; border-radius:10px; padding:8px 4px; text-align:center; }
.kicker-card span { display:block; font-size:10px; color:#0f766e; font-weight:800; }
.kicker-card strong { display:block; margin-top:2px; font-size:17px; color:#115e59; }
.bench-players { display:flex; flex-direction:column; align-items:center; gap:7px; overflow:auto; min-height:0; flex:1; padding:3px 0; }
.bench-player { flex:0 0 auto; width:38px; height:38px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:900; font-size:14px; border:3px solid #fff; box-shadow:0 2px 7px rgba(15,23,42,.2); }
.next-kicker { width:100%; min-height:40px; height:auto; padding:7px 5px; border-color:#0f766e; color:#0f766e; background:#f0fdfa; font-size:11px; }
.safe-count { text-align:center; border-radius:9px; padding:7px 4px; background:#fefce8; color:#854d0e; font-size:10px; font-weight:900; border:1px solid #fde68a; }
.safe-count.warn { background:#fff1f2; color:#be123c; border-color:#fecdd3; }
.bench-help { font-size:9px; line-height:1.4; color:#64748b; text-align:center; }
.kr-footer { display:flex; gap:16px; align-items:center; padding:9px 4px 0; color:#64748b; font-size:12px; }
.kr-footer span:last-child { margin-left:auto; font-weight:700; }
.legend-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; }
.legend-dot.team-a { background:#2563eb; }
.legend-dot.team-b { background:#e11d48; }
@media (max-width: 900px) {
  .kr-shell { padding:10px; }
  .kr-main { grid-template-columns:160px minmax(0,1fr); gap:8px; }
  .kr-play-area { grid-template-columns:minmax(0,1fr) 104px; gap:7px; }
  .kr-field, .kr-bench { height:600px; }
  .kr-tool-group { padding:8px; }
  .kr-help { display:none; }
}
@media (max-width: 620px) {
  .kr-title { font-size:18px; }
  .kr-subtitle { display:none; }
  .kr-main { display:flex; flex-direction:column; }
  .kr-toolbar { width:100%; display:grid; grid-template-columns:1fr 1fr; }
  .kr-actions { grid-column:1 / -1; display:grid; grid-template-columns:1fr 1fr; }
  .kr-actions .kr-tool-label { grid-column:1 / -1; }
  .kr-play-area { grid-template-columns:minmax(0,1fr) 92px; gap:6px; }
  .kr-field, .kr-bench { height:540px; }
  .player { width:42px; height:42px; font-size:15px; }
  .bench-player { width:34px; height:34px; }
}
"""

BOARD_JS = r"""
export default function({ parentElement, data, setStateValue }) {
  const shell = parentElement.querySelector('.kr-shell');
  const field = parentElement.querySelector('#field');
  const layer = parentElement.querySelector('#playersLayer');
  const ball = parentElement.querySelector('#ball');
  const benchPlayers = parentElement.querySelector('#benchPlayers');
  const editable = Boolean(data?.editable);
  const strategyTeam = (data?.strategy_team === 'B') ? 'B' : 'A';

  if (shell.dataset.dragging === '1') return;

  // Keep a just-made host edit on screen until the server confirms the exact
  // change id. Viewer devices never keep local pending state, so every shared
  // server snapshot (including offense changes) is applied immediately.
  const pendingRoot = window.__kickrunPendingStates || (window.__kickrunPendingStates = {});
  const pendingKey = `kickrun:${strategyTeam}`;
  const incomingState = structuredClone(data?.board_state || {});
  const pending = pendingRoot[pendingKey];
  const incomingChangeId = String(incomingState.last_change_id || '');

  let state;
  if (editable && pending && incomingChangeId !== pending.changeId && Date.now() < pending.expiresAt) {
    state = structuredClone(pending.state);
  } else {
    state = incomingState;
    if (pending && (incomingChangeId === pending.changeId || Date.now() >= pending.expiresAt)) {
      delete pendingRoot[pendingKey];
    }
  }

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const safeCountNumber = (v) => clamp(Number.parseInt(v ?? 1, 10) || 1, 1, 12);

  function defaultPositions(team, count, offenseTeam) {
    if (team === offenseTeam) {
      return Array.from({length:count}, (_,i) => ({
        id:i+1,
        x:50,
        y:84,
        status:i === 0 ? 'field' : 'bench',
      }));
    }
    const rows = [[34,[18,34,50,66,82]],[46,[25,42,58,75]],[56,[35,50,65]]];
    const coords = [];
    rows.forEach(([y,xs]) => xs.forEach(x => coords.push({x:Number(x), y:Number(y)})));
    return Array.from({length:count}, (_,i) => ({id:i+1, ...coords[i], status:'field'}));
  }

  function ensureState() {
    state.counts = state.counts || {A:8,B:9};
    state.counts.A = safeCountNumber(state.counts.A);
    state.counts.B = safeCountNumber(state.counts.B);
    state.offense = ['A','B'].includes(state.offense) ? state.offense : strategyTeam;
    state.current_kicker = clamp(Number.parseInt(state.current_kicker ?? 1, 10) || 1, 1, state.counts[state.offense]);
    state.players = state.players || {A:[],B:[]};

    ['A','B'].forEach(team => {
      const target = state.counts[team];
      const defaults = defaultPositions(team, target, state.offense);
      const old = Array.isArray(state.players[team]) ? state.players[team] : [];
      const mapped = new Map(old.map(p => [Number(p.id), p]));
      state.players[team] = Array.from({length:target}, (_,i) => {
        const id = i + 1;
        const prev = mapped.get(id);
        if (!prev) return defaults[i];
        let status = ['field','bench'].includes(prev.status) ? prev.status : defaults[i].status;
        if (team !== state.offense) status = 'field';
        return {
          id,
          x:clamp(Number(prev.x)||defaults[i].x,2,98),
          y:clamp(Number(prev.y)||defaults[i].y,2,98),
          status,
        };
      });
    });

    const kicker = state.players[state.offense].find(p => p.id === state.current_kicker);
    if (kicker && kicker.status !== 'field') {
      kicker.status = 'field';
      kicker.x = 50;
      kicker.y = 84;
    }

    state.ball = state.ball || {x:50,y:78};
    state.ball.x = clamp(Number(state.ball.x)||50,2,98);
    state.ball.y = clamp(Number(state.ball.y)||78,2,98);
  }

  function commit() {
    if (!editable) return;
    const changeId = `${strategyTeam}:${Date.now()}:${Math.random().toString(36).slice(2,9)}`;
    state.client_change_id = changeId;
    state.updated_at_client = Date.now();
    const outgoing = structuredClone(state);
    pendingRoot[pendingKey] = {
      state: outgoing,
      changeId,
      expiresAt: Date.now() + 3500,
    };
    setStateValue('board_state', outgoing);
  }

  function coordsFromPointer(ev) {
    const rect = field.getBoundingClientRect();
    return {
      x: clamp(((ev.clientX - rect.left) / rect.width) * 100, 2, 98),
      y: clamp(((ev.clientY - rect.top) / rect.height) * 100, 2, 98),
    };
  }

  function makeDraggable(el, target) {
    if (!editable) {
      el.style.cursor = 'default';
      return;
    }
    let pointerId = null;
    el.onpointerdown = (ev) => {
      ev.preventDefault();
      pointerId = ev.pointerId;
      shell.dataset.dragging = '1';
      el.setPointerCapture(pointerId);
    };
    el.onpointermove = (ev) => {
      if (pointerId !== ev.pointerId || !el.hasPointerCapture(pointerId)) return;
      const pos = coordsFromPointer(ev);
      target.x = pos.x; target.y = pos.y;
      target.status = 'field';
      el.style.left = `${target.x}%`;
      el.style.top = `${target.y}%`;
    };
    const finish = (ev) => {
      if (pointerId !== ev.pointerId) return;
      try { el.releasePointerCapture(pointerId); } catch (_) {}
      pointerId = null;
      shell.dataset.dragging = '0';
      renderBench();
      commit();
    };
    el.onpointerup = finish;
    el.onpointercancel = finish;
  }

  function isInSafeZone(player) {
    return player.status === 'field' && player.x >= 16 && player.x <= 84 && player.y >= 3 && player.y <= 22;
  }

  function offenseSafeCount() {
    return state.players[state.offense].filter(isInSafeZone).length;
  }

  function renderMarkers() {
    layer.innerHTML = '';
    ['A','B'].forEach(team => {
      state.players[team].forEach(player => {
        if (player.status !== 'field') return;
        const el = document.createElement('div');
        el.className = `player team-${team.toLowerCase()}`;
        if (team === state.offense) el.classList.add('offense');
        if (team === strategyTeam) el.classList.add('own');
        if (team === state.offense && player.id === state.current_kicker) el.classList.add('current-kicker');
        el.textContent = player.id;
        el.style.left = `${player.x}%`;
        el.style.top = `${player.y}%`;
        el.title = `${team}팀 ${player.id}번`;
        makeDraggable(el, player);
        layer.appendChild(el);
      });
    });
    ball.style.left = `${state.ball.x}%`;
    ball.style.top = `${state.ball.y}%`;
    makeDraggable(ball, state.ball);
  }

  function renderBench() {
    const offense = state.offense;
    const emoji = offense === 'A' ? '🔵' : '🔴';
    parentElement.querySelector('#benchTeam').textContent = `${emoji} ${offense}팀 대기`;
    parentElement.querySelector('#currentKickerLabel').textContent = `${state.current_kicker}번`;
    benchPlayers.innerHTML = '';

    state.players[offense]
      .filter(player => player.status === 'bench')
      .forEach(player => {
        const el = document.createElement('div');
        el.className = `bench-player team-${offense.toLowerCase()}`;
        el.textContent = player.id;
        el.title = `${offense}팀 ${player.id}번 대기`;
        benchPlayers.appendChild(el);
      });

    const count = offenseSafeCount();
    const safeEl = parentElement.querySelector('#safeCount');
    safeEl.textContent = `안전지대 ${count} / 3`;
    safeEl.classList.toggle('warn', count > 3);

    const next = parentElement.querySelector('#nextKicker');
    const isLast = state.current_kicker >= state.counts[offense];
    next.disabled = !editable || isLast;
    next.textContent = isLast ? '마지막 키커' : `다음 키커 ${state.current_kicker + 1}번 ▶`;
    next.onclick = () => {
      if (!editable || isLast) return;
      state.current_kicker += 1;
      const nextPlayer = state.players[offense].find(p => p.id === state.current_kicker);
      if (nextPlayer) {
        nextPlayer.status = 'field';
        nextPlayer.x = 50;
        nextPlayer.y = 84;
      }
      renderMarkers();
      renderBench();
      commit();
    };
  }

  function resetForOffense(offenseTeam) {
    state.offense = offenseTeam;
    state.current_kicker = 1;
    state.players.A = defaultPositions('A', state.counts.A, offenseTeam);
    state.players.B = defaultPositions('B', state.counts.B, offenseTeam);
    state.ball = {x:50,y:78};
  }

  function renderControls() {
    parentElement.querySelector('#roomTitle').textContent = `${strategyTeam}팀 작전실 · 킥앤런 작전판`;
    parentElement.querySelector('#countA').textContent = state.counts.A;
    parentElement.querySelector('#countB').textContent = state.counts.B;
    parentElement.querySelector('#modeText').textContent = editable ? '✏️ 편집 가능' : '👀 보기 전용';

    parentElement.querySelectorAll('[data-count-team]').forEach(btn => {
      btn.disabled = !editable;
      btn.onclick = () => {
        if (!editable) return;
        const team = btn.dataset.countTeam;
        const delta = Number(btn.dataset.delta || 0);
        state.counts[team] = safeCountNumber(state.counts[team] + delta);
        ensureState();
        renderControls(); renderMarkers(); renderBench(); commit();
      };
    });

    parentElement.querySelectorAll('[data-offense]').forEach(btn => {
      btn.disabled = !editable;
      btn.classList.toggle('active', btn.dataset.offense === state.offense);
      btn.onclick = () => {
        if (!editable) return;
        const nextOffense = btn.dataset.offense;
        if (nextOffense === state.offense) return;
        resetForOffense(nextOffense);
        renderControls(); renderMarkers(); renderBench(); commit();
      };
    });

    const ballHome = parentElement.querySelector('#ballHome');
    const resetBoard = parentElement.querySelector('#resetBoard');
    ballHome.disabled = !editable;
    resetBoard.disabled = !editable;
    ballHome.onclick = () => {
      if (!editable) return;
      state.ball = {x:50,y:78};
      renderMarkers(); commit();
    };
    resetBoard.onclick = () => {
      if (!editable) return;
      resetForOffense(state.offense);
      renderMarkers(); renderBench(); commit();
    };
  }

  ensureState();
  renderControls();
  renderMarkers();
  renderBench();
}
"""

TACTICS_BOARD = st.components.v2.component(
    name="kickrun_tactics_board_v4",
    html=BOARD_HTML,
    css=BOARD_CSS,
    js=BOARD_JS,
)


def persist_component_state(team: str, key: str, client_id: str, editable: bool) -> None:
    if not editable or not STORE.is_controller(team, client_id):
        return
    result = st.session_state.get(key)
    incoming = getattr(result, "board_state", None) if result is not None else None
    if isinstance(incoming, dict):
        STORE.update_board(team, incoming, client_id=client_id)


def show_board(team: str, *, client_id: str, key_suffix: str, height: int = 760) -> None:
    component_key = f"kr_board_{team}_{key_suffix}"

    @st.fragment(run_every=0.8)
    def live_board() -> None:
        editable = STORE.is_controller(team, client_id)
        if editable:
            STORE.touch_controller(team, client_id)
        snapshot = STORE.snapshot(team)

        def on_board_state_change() -> None:
            persist_component_state(team, component_key, client_id, editable)

        TACTICS_BOARD(
            data={
                "board_state": snapshot,
                "strategy_team": team,
                "editable": editable,
            },
            default={"board_state": snapshot},
            on_board_state_change=on_board_state_change,
            key=component_key,
            width="stretch",
            height=height,
        )

    live_board()


def show_controller_bar(team: str, client_id: str) -> None:
    @st.fragment(run_every=1.0)
    def controller_bar() -> None:
        is_host = STORE.is_controller(team, client_id)
        if is_host:
            STORE.touch_controller(team, client_id)
            c1, c2 = st.columns([4, 1])
            with c1:
                st.success("✏️ 이 기기가 현재 작전판 조작자입니다. 다른 팀원 기기는 보기 전용으로 자동 동기화됩니다.")
            with c2:
                if st.button("조작권 놓기", key=f"release_{team}_{client_id}", use_container_width=True):
                    STORE.release_controller(team, client_id)
                    st.rerun(scope="fragment")
            return

        status = STORE.controller_status(team)
        if status["active"]:
            st.info("👀 다른 팀원 기기가 작전판을 조작 중입니다. 이 기기는 보기 전용이며 변경 내용이 자동 반영됩니다.")
            return

        c1, c2 = st.columns([4, 1])
        with c1:
            st.info("👀 현재 작전판 조작자가 없습니다. 한 기기만 조작권을 가져가서 작전을 수정하세요.")
        with c2:
            if st.button("✏️ 조작권 가져오기", key=f"claim_{team}_{client_id}", type="primary", use_container_width=True):
                STORE.claim_controller(team, client_id)
                st.rerun(scope="fragment")

    controller_bar()


def go_to(role: str) -> None:
    st.query_params["team"] = role
    st.rerun()


role_raw = st.query_params.get("team", "")
role = str(role_raw).upper() if role_raw is not None else ""

if "kickrun_client_id" not in st.session_state:
    st.session_state["kickrun_client_id"] = uuid4().hex
client_id = str(st.session_state["kickrun_client_id"])

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.35rem; padding-bottom: 2rem; max-width: 1120px; }
      h1, h2, h3 { letter-spacing: -0.035em; }
      div[data-testid="stButton"] button { border-radius: 12px; font-weight: 750; }
    </style>
    """,
    unsafe_allow_html=True,
)

if role not in {"A", "B", "T"}:
    st.title("⚽ 킥앤런 디지털 작전판")
    st.write("팀을 선택하면 해당 팀의 **비공개 작전실**로 들어갑니다. 같은 팀 태블릿은 같은 작전판 상태를 공유합니다.")
    st.info("현재 버전: 팀별 1대만 조작 · 나머지는 실시간 보기 · 공격팀 전환 공유 · 키커/대기석 · 안전지대 3자리 · 선수/공 자유 이동")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔵 A팀")
        st.caption("A팀 공유 작전실 · 한 기기만 조작권 사용")
        if st.button("A팀 작전실 입장", use_container_width=True, type="primary"):
            go_to("A")
    with c2:
        st.subheader("🔴 B팀")
        st.caption("B팀 공유 작전실 · 한 기기만 조작권 사용")
        if st.button("B팀 작전실 입장", use_container_width=True, type="primary"):
            go_to("B")
    with c3:
        st.subheader("👨‍🏫 교사")
        st.caption("두 팀 작전판을 보기 전용으로 확인")
        if st.button("교사용 화면 입장", use_container_width=True):
            go_to("T")

    st.divider()
    st.markdown("**배포 후 QR 주소 예시**")
    st.code("https://내앱주소.streamlit.app/?team=A\nhttps://내앱주소.streamlit.app/?team=B")
    st.stop()

with st.sidebar:
    st.markdown("### ⚽ 킥앤런 작전판")
    if role == "T":
        st.caption("교사용 보기 화면")
    else:
        st.caption(f"{role}팀 작전실")
    if st.button("↩ 입장 화면으로", use_container_width=True):
        st.query_params.clear()
        st.rerun()

    if role == "T":
        st.divider()
        st.warning("전체 초기화는 수업 시작 직전에만 사용하세요.")
        if st.button("🧹 모든 작전판 초기화", use_container_width=True):
            STORE.reset_all()
            st.success("A/B팀 작전판과 인원수를 초기화했습니다.")
            st.rerun()

        st.divider()
        st.caption("조작 기기가 멈추거나 닫혔을 때만 사용하세요.")
        c_unlock_a, c_unlock_b = st.columns(2)
        with c_unlock_a:
            if st.button("A 조작권 해제", use_container_width=True):
                STORE.release_controller("A", force=True)
                st.rerun()
        with c_unlock_b:
            if st.button("B 조작권 해제", use_container_width=True):
                STORE.release_controller("B", force=True)
                st.rerun()

if role in {"A", "B"}:
    st.title(f"{'🔵' if role == 'A' else '🔴'} {role}팀 작전실")
    st.caption("한 기기만 조작권을 가지고 작전판을 움직입니다. 같은 팀의 다른 태블릿은 약 0.8초 안팎으로 같은 상태를 봅니다.")
    show_controller_bar(role, client_id)
    show_board(role, client_id=client_id, key_suffix="student", height=760)
    st.caption("※ 조작 기기가 화면을 닫으면 약 15초 뒤 조작권이 자동으로 풀립니다. Streamlit 앱이 재시작되면 작전판도 초기화됩니다.")
else:
    st.title("👨‍🏫 교사용 모니터")
    st.caption("학생 작전판을 건드리지 않고 실시간으로 확인합니다.")
    selected = st.radio("확인할 팀", ["A", "B"], horizontal=True, format_func=lambda x: f"{'🔵' if x == 'A' else '🔴'} {x}팀")
    show_board(selected, client_id=f"teacher-{client_id}", key_suffix="teacher", height=760)
