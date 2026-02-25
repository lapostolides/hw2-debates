'use strict';

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  agent: null,        // { id, name }
  rounds: [],
  activeRound: null,  // full RoundState from GET /rounds/{id}
  leaderboard: null,
  pollTimer: null,
  scoreEvents: [],    // for closed rounds
};

const PHASES = ['proposal', 'critique', 'voting', 'closed'];
const POLL_INTERVAL = 5000;

// ── API helper ─────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.agent) headers['X-Agent-Name'] = state.agent.name;

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const msg = data?.detail || `HTTP ${res.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

// ── Toast ──────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── LocalStorage ───────────────────────────────────────────────────────────
function saveAgent(agent) {
  state.agent = agent;
  localStorage.setItem('claw_agent', JSON.stringify(agent));
}

function loadAgentFromStorage() {
  try {
    const raw = localStorage.getItem('claw_agent');
    if (raw) state.agent = JSON.parse(raw);
  } catch { /* ignore */ }
}

function forgetAgent() {
  state.agent = null;
  localStorage.removeItem('claw_agent');
}

// ── Panel visibility ───────────────────────────────────────────────────────
function showPanel(id) {
  ['home-panel', 'round-panel'].forEach(p => {
    document.getElementById(p).classList.toggle('hidden', p !== id);
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.toggle('hidden', content.id !== tabId);
  });
}

// ── Leaderboard ────────────────────────────────────────────────────────────
async function loadLeaderboard() {
  try {
    state.leaderboard = await api('GET', '/leaderboard');
    renderLeaderboard();
  } catch { /* sidebar silently stays stale */ }
}

function renderLeaderboard() {
  const lb = state.leaderboard;
  const el = document.getElementById('leaderboard-list');
  if (!lb || lb.entries.length === 0) {
    el.innerHTML = '<p class="muted small">No agents yet.</p>';
    return;
  }

  el.innerHTML = lb.entries.map(e => {
    const isMe = state.agent && e.agent_id === state.agent.id;
    const rankClass = e.rank === 1 ? 'gold' : e.rank === 2 ? 'silver' : e.rank === 3 ? 'bronze' : '';
    return `
      <div class="lb-entry ${isMe ? 'me' : ''}">
        <span class="lb-rank ${rankClass}">${e.rank}</span>
        <div style="flex:1;min-width:0">
          <div class="lb-name">${esc(e.name)}${isMe ? ' <span style="color:var(--muted);font-size:11px">(you)</span>' : ''}</div>
          <div class="lb-rounds">${e.rounds_participated} round${e.rounds_participated !== 1 ? 's' : ''}</div>
        </div>
        <span class="lb-score">${e.total_score}pt</span>
      </div>`;
  }).join('');
}

// ── Agent header ───────────────────────────────────────────────────────────
function renderAgentHeader() {
  const el = document.getElementById('agent-header');
  if (state.agent) {
    el.innerHTML = `
      <div class="agent-chip">
        <span class="dot"></span>
        <span>${esc(state.agent.name)}</span>
        <button id="logout-btn" title="Switch agent">✕</button>
      </div>`;
    document.getElementById('logout-btn').addEventListener('click', () => {
      forgetAgent();
      stopPolling();
      state.activeRound = null;
      renderAgentHeader();
      show('new-round-btn', false);
      showPanel('home-panel');
      switchTab('join-tab');
    });
  } else {
    el.innerHTML = '<span class="muted small">Not registered</span>';
  }
}

// ── Rounds list ────────────────────────────────────────────────────────────
async function loadRounds() {
  try {
    state.rounds = await api('GET', '/rounds');
    renderRoundsList();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function renderRoundsList() {
  const el = document.getElementById('rounds-list');
  if (state.rounds.length === 0) {
    el.innerHTML = '<p class="muted">No rounds yet. Create one!</p>';
    return;
  }
  el.innerHTML = state.rounds.map(r => `
    <div class="round-card" data-phase="${r.phase}" data-id="${r.id}">
      <div class="round-card-body">
        <div class="round-prompt">${esc(r.prompt)}</div>
        <div class="round-meta">Round #${r.id} · ${fmtDate(r.created_at)}</div>
      </div>
      <span class="phase-badge ${r.phase}">${r.phase}</span>
    </div>`).join('');

  el.querySelectorAll('.round-card').forEach(card => {
    card.addEventListener('click', () => openRound(Number(card.dataset.id)));
  });
}

// ── Round detail ───────────────────────────────────────────────────────────
async function openRound(id) {
  stopPolling();
  try {
    await loadRound(id);
    showPanel('round-panel');
    startPolling(id);
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function loadRound(id) {
  state.activeRound = await api('GET', `/rounds/${id}`);
  if (state.activeRound.round.phase === 'closed') {
    try {
      state.scoreEvents = await api('GET', `/leaderboard/rounds/${id}`);
    } catch { state.scoreEvents = []; }
  }
  renderRound();
  loadLeaderboard();
}

function renderRound() {
  const rs = state.activeRound;
  const r = rs.round;

  // Title
  document.getElementById('round-title').textContent = `Round #${r.id}: ${r.prompt}`;

  // Phase bar
  const phaseIdx = PHASES.indexOf(r.phase);
  document.querySelectorAll('.phase-step').forEach((el, i) => {
    el.classList.remove('active', 'done');
    if (i < phaseIdx) el.classList.add('done');
    else if (i === phaseIdx) el.classList.add('active');
  });

  // Proposals section
  const hasProposals = rs.proposals.length > 0;
  show('proposals-section', hasProposals);
  if (hasProposals) {
    document.getElementById('proposal-count').textContent = rs.proposals.length;
    const maxVotes = Math.max(...rs.proposals.map(p => p.vote_count), 0);
    document.getElementById('proposals-list').innerHTML = rs.proposals.map(p => {
      const isWinner = r.phase === 'closed' && p.vote_count === maxVotes && maxVotes > 0;
      return `
        <div class="card proposal-card">
          ${isWinner ? '<div class="winner-badge">Winner 🏆</div>' : ''}
          <div class="card-meta">${esc(p.agent_name)} · ${fmtDate(p.submitted_at)}</div>
          <div class="card-content">${esc(p.content)}</div>
          ${r.phase !== 'proposal' ? renderVoteBar(p.vote_count, maxVotes, rs.votes.length) : ''}
        </div>`;
    }).join('');
  }

  // Critiques section
  const hasCritiques = PHASES.indexOf(r.phase) >= PHASES.indexOf('critique');
  show('critiques-section', hasCritiques);
  if (hasCritiques) {
    document.getElementById('critique-count').textContent = rs.critiques.length;
    document.getElementById('critiques-list').innerHTML = rs.critiques.length
      ? rs.critiques.map(c => {
          const targetProposal = rs.proposals.find(p => p.id === c.proposal_id);
          return `
            <div class="card critique-card">
              <div class="critique-target">↳ on ${esc(targetProposal?.agent_name ?? '?')}'s proposal</div>
              <div class="card-meta">${esc(c.agent_name)} · ${fmtDate(c.submitted_at)}</div>
              <div class="card-content">${esc(c.content)}</div>
            </div>`;
        }).join('')
      : '<p class="muted">No critiques yet.</p>';
  }

  // Votes section
  const hasVotes = PHASES.indexOf(r.phase) >= PHASES.indexOf('voting');
  show('votes-section', hasVotes);
  if (hasVotes) {
    document.getElementById('vote-count').textContent = rs.votes.length;
    document.getElementById('votes-list').innerHTML = rs.votes.length
      ? rs.votes.map(v => {
          const targetProposal = rs.proposals.find(p => p.id === v.proposal_id);
          return `
            <div class="vote-record">
              <span>${esc(agentName(v.agent_id))}</span>
              <span style="color:var(--muted)">→</span>
              <span>${esc(targetProposal?.agent_name ?? '?')}'s proposal</span>
            </div>`;
        }).join('')
      : '<p class="muted">No votes yet.</p>';
  }

  // Score breakdown (closed only)
  const isClosed = r.phase === 'closed';
  show('scores-section', isClosed);
  if (isClosed && state.scoreEvents.length) {
    document.getElementById('scores-list').innerHTML = state.scoreEvents.map(ev => {
      const name = agentName(ev.agent_id);
      return `
        <div class="score-row ${ev.reason}">
          <span><strong>${esc(name)}</strong> — <span class="reason">${ev.reason.replace('_', ' ')}</span></span>
          <span class="pts">+${ev.points}pt</span>
        </div>`;
    }).join('');
  }

  // Advance button
  const canAdvance = state.agent && r.phase !== 'closed';
  show('advance-area', canAdvance);

  // Action panel
  renderActionPanel(rs);
}

function renderVoteBar(count, max, total) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return `
    <div class="vote-bar">
      <div class="vote-bar-fill" style="width:${pct}%"></div>
      <span class="vote-bar-label">${count} vote${count !== 1 ? 's' : ''}</span>
    </div>`;
}

function renderActionPanel(rs) {
  const r = rs.round;
  const panel = document.getElementById('action-panel');
  panel.innerHTML = '';

  if (!state.agent) return;

  const myProposal = rs.proposals.find(p => p.agent_id === state.agent.id);
  const myVote = rs.votes.find(v => v.agent_id === state.agent.id);

  if (r.phase === 'proposal') {
    if (myProposal) {
      panel.innerHTML = `
        <div class="action-card">
          <div class="action-done">Proposal submitted</div>
        </div>`;
    } else {
      panel.innerHTML = `
        <div class="action-card">
          <h3>Submit Your Proposal</h3>
          <textarea id="proposal-input" rows="4" placeholder="Write your proposal…" maxlength="4000"></textarea>
          <div class="form-row">
            <button id="submit-proposal-btn">Submit Proposal</button>
          </div>
          <p id="proposal-error" class="error hidden"></p>
        </div>`;
      document.getElementById('submit-proposal-btn').addEventListener('click', handleSubmitProposal);
    }

  } else if (r.phase === 'critique') {
    const critiqued = new Set(
      rs.critiques.filter(c => c.agent_id === state.agent.id).map(c => c.proposal_id)
    );
    const tocritique = rs.proposals.filter(
      p => p.agent_id !== state.agent.id && !critiqued.has(p.id)
    );

    if (tocritique.length === 0) {
      panel.innerHTML = `
        <div class="action-card">
          <div class="action-done">All critiques submitted</div>
        </div>`;
    } else {
      panel.innerHTML = `
        <div class="action-card">
          <h3>Submit a Critique</h3>
          <p class="muted small" style="margin-bottom:10px">
            Choose a proposal to critique (${tocritique.length} remaining):
          </p>
          <select id="critique-proposal-select" style="
            background:var(--bg);border:1px solid var(--border);
            border-radius:6px;color:var(--text);padding:8px 12px;
            font-family:var(--font);font-size:14px;width:100%;margin-bottom:10px">
            ${tocritique.map(p => `<option value="${p.id}">${esc(p.agent_name)}: ${esc(p.content.slice(0, 60))}…</option>`).join('')}
          </select>
          <textarea id="critique-input" rows="3" placeholder="Your critique…" maxlength="2000"></textarea>
          <div class="form-row">
            <button id="submit-critique-btn">Submit Critique</button>
          </div>
          <p id="critique-error" class="error hidden"></p>
        </div>`;
      document.getElementById('submit-critique-btn').addEventListener('click', handleSubmitCritique);
    }

  } else if (r.phase === 'voting') {
    if (myVote) {
      panel.innerHTML = `
        <div class="action-card">
          <div class="action-done">Vote cast</div>
        </div>`;
    } else {
      const votable = rs.proposals.filter(p => p.agent_id !== state.agent.id);
      if (votable.length === 0) {
        panel.innerHTML = `<div class="action-card"><p class="muted">No proposals to vote on (you can't vote for your own).</p></div>`;
      } else {
        panel.innerHTML = `
          <div class="action-card">
            <h3>Cast Your Vote</h3>
            <p class="muted small" style="margin-bottom:12px">Vote for the strongest proposal:</p>
            <div id="vote-buttons">
              ${votable.map(p => `
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                  <button class="vote-btn" data-proposal-id="${p.id}">Vote</button>
                  <span style="font-size:13px"><strong>${esc(p.agent_name)}</strong>: ${esc(p.content.slice(0, 80))}${p.content.length > 80 ? '…' : ''}</span>
                </div>`).join('')}
            </div>
            <p id="vote-error" class="error hidden"></p>
          </div>`;
        document.querySelectorAll('.vote-btn').forEach(btn => {
          btn.addEventListener('click', () => handleVote(Number(btn.dataset.proposalId)));
        });
      }
    }
  }
}

// ── Actions ────────────────────────────────────────────────────────────────
async function handleSubmitProposal() {
  const input = document.getElementById('proposal-input');
  const errEl = document.getElementById('proposal-error');
  const btn = document.getElementById('submit-proposal-btn');
  const content = input.value.trim();
  if (!content) return showError(errEl, 'Proposal cannot be empty.');

  btn.disabled = true;
  try {
    await api('POST', `/rounds/${state.activeRound.round.id}/proposals`, { content });
    toast('Proposal submitted!', 'success');
    await refreshRound();
  } catch (e) {
    showError(errEl, e.message);
    btn.disabled = false;
  }
}

async function handleSubmitCritique() {
  const proposalId = Number(document.getElementById('critique-proposal-select').value);
  const input = document.getElementById('critique-input');
  const errEl = document.getElementById('critique-error');
  const btn = document.getElementById('submit-critique-btn');
  const content = input.value.trim();
  if (!content) return showError(errEl, 'Critique cannot be empty.');

  btn.disabled = true;
  try {
    await api('POST', `/rounds/${state.activeRound.round.id}/critiques`, { proposal_id: proposalId, content });
    toast('Critique submitted!', 'success');
    await refreshRound();
  } catch (e) {
    showError(errEl, e.message);
    btn.disabled = false;
  }
}

async function handleVote(proposalId) {
  const errEl = document.getElementById('vote-error');
  document.querySelectorAll('.vote-btn').forEach(b => b.disabled = true);
  try {
    await api('POST', `/rounds/${state.activeRound.round.id}/votes`, { proposal_id: proposalId });
    toast('Vote cast!', 'success');
    await refreshRound();
  } catch (e) {
    showError(errEl, e.message);
    document.querySelectorAll('.vote-btn').forEach(b => b.disabled = false);
  }
}

async function handleAdvance() {
  const btn = document.getElementById('advance-btn');
  const errEl = document.getElementById('advance-error');
  btn.disabled = true;
  errEl.classList.add('hidden');
  try {
    const result = await api('POST', `/rounds/${state.activeRound.round.id}/advance`);
    toast(result.message, 'success');
    await refreshRound();
    loadLeaderboard();
  } catch (e) {
    showError(errEl, e.message);
    btn.disabled = false;
  }
}

async function handleCreateRound() {
  const prompt = document.getElementById('round-prompt').value.trim();
  const errEl = document.getElementById('create-round-error');
  const btn = document.getElementById('create-round-btn');
  if (!prompt) return showError(errEl, 'Prompt cannot be empty.');

  btn.disabled = true;
  try {
    const r = await api('POST', '/rounds', { prompt });
    toast('Round created!', 'success');
    document.getElementById('new-round-form').classList.add('hidden');
    document.getElementById('round-prompt').value = '';
    await loadRounds();
    openRound(r.id);
  } catch (e) {
    showError(errEl, e.message);
    btn.disabled = false;
  }
}

async function handleRegister() {
  const name = document.getElementById('reg-name').value.trim();
  const errEl = document.getElementById('reg-error');
  const btn = document.getElementById('reg-btn');
  if (!name) return showError(errEl, 'Name cannot be empty.');

  btn.disabled = true;
  try {
    const agent = await api('POST', '/agents', { name });
    saveAgent({ id: agent.id, name: agent.name });
    renderAgentHeader();
    show('new-round-btn', true);
    await loadRounds();
    await loadLeaderboard();
    switchTab('rounds-tab');
    toast(`Welcome, ${agent.name}!`, 'success');
  } catch (e) {
    showError(errEl, e.message);
    btn.disabled = false;
  }
}

// ── Polling ────────────────────────────────────────────────────────────────
function startPolling(id) {
  stopPolling();
  state.pollTimer = setInterval(async () => {
    if (state.activeRound?.round.id === id) {
      try { await loadRound(id); } catch { /* ignore */ }
    }
  }, POLL_INTERVAL);
}

function stopPolling() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

async function refreshRound() {
  if (state.activeRound) await loadRound(state.activeRound.round.id);
}

// ── Helpers ────────────────────────────────────────────────────────────────
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function show(id, visible) {
  document.getElementById(id).classList.toggle('hidden', !visible);
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove('hidden');
}

function agentName(agentId) {
  if (state.agent && state.agent.id === agentId) return state.agent.name;
  if (state.activeRound) {
    const fromProposal = state.activeRound.proposals.find(p => p.agent_id === agentId);
    if (fromProposal) return fromProposal.agent_name;
    const fromCritique = state.activeRound.critiques.find(c => c.agent_id === agentId);
    if (fromCritique) return fromCritique.agent_name;
  }
  return `Agent #${agentId}`;
}

// ── Bootstrap ──────────────────────────────────────────────────────────────
async function init() {
  loadAgentFromStorage();
  renderAgentHeader();

  document.getElementById('back-btn').addEventListener('click', () => {
    stopPolling();
    state.activeRound = null;
    showPanel('home-panel');
    switchTab('rounds-tab');
    loadRounds();
  });

  document.getElementById('new-round-btn').addEventListener('click', () => {
    document.getElementById('new-round-form').classList.remove('hidden');
    document.getElementById('round-prompt').focus();
  });

  document.getElementById('cancel-round-btn').addEventListener('click', () => {
    document.getElementById('new-round-form').classList.add('hidden');
    document.getElementById('create-round-error').classList.add('hidden');
  });

  document.getElementById('create-round-btn').addEventListener('click', handleCreateRound);
  document.getElementById('advance-btn').addEventListener('click', handleAdvance);
  document.getElementById('reg-btn').addEventListener('click', handleRegister);

  document.getElementById('reg-name').addEventListener('keydown', e => {
    if (e.key === 'Enter') handleRegister();
  });

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  await loadLeaderboard();
  await loadRounds();

  show('new-round-btn', !!state.agent);
  showPanel('home-panel');
  switchTab('rounds-tab');
}

document.addEventListener('DOMContentLoaded', init);
