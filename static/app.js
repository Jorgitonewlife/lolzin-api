/* lolzin-api landing page: sync trigger + performance views. */

const $ = (selector) => document.querySelector(selector);
const state = { source: '' };

const escapeHtml = (value) =>
  String(value ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const orDash = (value) =>
  (value === null || value === undefined || value === '') ? '—' : escapeHtml(value);

const shortDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

async function getJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

/** Append the active source filter to a stats path. */
function withSource(path) {
  return state.source ? `${path}?source=${encodeURIComponent(state.source)}` : path;
}

function renderMatches(matches) {
  const body = $('#matches');
  if (!matches.length) {
    body.innerHTML = '<tr><td colspan="8" class="empty">No matches recorded yet.</td></tr>';
    return;
  }
  body.innerHTML = matches.map((m) => `
    <tr>
      <td>${shortDate(m.played_at)}</td>
      <td>${escapeHtml(m.champion_name)}</td>
      <td class="num">${m.kills} / ${m.deaths} / ${m.assists}</td>
      <td class="num">${m.kda}</td>
      <td class="${m.victory ? 'win' : 'loss'}">${m.victory ? 'Win' : 'Loss'}</td>
      <td class="num">${m.duration_minutes}m</td>
      <td class="items-cell">${m.item_names.map(escapeHtml).join(', ') || '—'}</td>
      <td><span class="badge ${escapeHtml(m.source)}">${escapeHtml(m.source)}</span></td>
    </tr>
  `).join('');
}

function renderChampionPerformance(rows) {
  const body = $('#champion-performance');
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty">No matches in this window.</td></tr>';
    return;
  }
  body.innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.name)}</td>
      <td>${orDash(r.role)}</td>
      <td class="num">${r.games}</td>
      <td class="num">${r.wins}</td>
      <td class="num">${r.win_rate}%</td>
      <td class="num">${r.avg_kda}</td>
      <td>${shortDate(r.last_played)}</td>
    </tr>
  `).join('');

  const select = $('#trend-champion');
  const previous = select.value;
  select.innerHTML = '<option value="">All champions</option>' + rows.map((r) =>
    `<option value="${r.champion_id}">${escapeHtml(r.name)}</option>`).join('');
  // Keep the picked champion only while it is still on offer.
  const stillAvailable = Array.from(select.options).some((o) => o.value === previous);
  select.value = stillAvailable ? previous : '';
}

function renderItemPerformance(rows) {
  const body = $('#item-performance');
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">No items recorded yet.</td></tr>';
    return;
  }
  body.innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.name)}</td>
      <td>${orDash(r.category)}</td>
      <td class="num">${r.games}</td>
      <td class="num">${r.wins}</td>
      <td class="num">${r.win_rate}%</td>
      <td class="num">${r.avg_kda}</td>
    </tr>
  `).join('');
}

function renderTimeline(points) {
  const host = $('#timeline');
  if (!points.length) {
    host.innerHTML = '<p class="empty">No matches in this window yet.</p>';
    return;
  }
  host.innerHTML = points.map((p) => `
    <div class="trend-row">
      <span class="trend-label">${shortDate(p.period)}</span>
      <div class="bar"><i style="width:${p.win_rate}%"></i></div>
      <span class="trend-value">${p.games} games · ${p.win_rate}% · ${p.avg_kda} KDA</span>
    </div>
  `).join('');
}

function renderChampions(champions) {
  $('#champions').innerHTML = champions.map((c) => `
    <div class="card">
      <div class="row">
        <div>
          <div class="name">${escapeHtml(c.name)}</div>
          <div class="title">${orDash(c.title)}</div>
        </div>
        <span class="tag">${orDash(c.role)}</span>
      </div>
      <div class="meta">
        <span>${orDash(c.region)}</span>
        <span>Difficulty ${c.difficulty ?? '—'}</span>
        <span>${orDash(c.release_year)}</span>
      </div>
    </div>
  `).join('');
}

function renderRoles(rows) {
  $('#stats').innerHTML = rows.map((r) => `
    <tr>
      <td>${escapeHtml(r.role)}</td>
      <td class="num">${r.champions}</td>
      <td class="num">${r.matches}</td>
      <td class="num">${r.wins}</td>
      <td class="num">${r.win_rate}%</td>
      <td class="num">${r.avg_kda}</td>
    </tr>
  `).join('');
}

/* Two fast filter changes can leave responses arriving out of order; each
   loader ignores its own results once a newer request has started. */
let loadGeneration = 0;
let timelineGeneration = 0;

async function loadTimeline() {
  const generation = ++timelineGeneration;
  const championId = $('#trend-champion').value;
  const params = new URLSearchParams();
  if (state.source) params.set('source', state.source);
  if (championId) params.set('champion_id', championId);
  const query = params.toString();

  const points = await getJSON(`/api/stats/timeline${query ? `?${query}` : ''}`);
  if (generation !== timelineGeneration) return;
  renderTimeline(points);
}

async function loadAll() {
  const generation = ++loadGeneration;
  const matchParams = new URLSearchParams({ limit: '15' });
  if (state.source) matchParams.set('source', state.source);

  try {
    const [champions, roles, matches, championPerf, itemPerf] = await Promise.all([
      getJSON('/api/champions?limit=200'),
      getJSON('/api/stats/roles'),
      getJSON(`/api/matches?${matchParams}`),
      getJSON(withSource('/api/stats/champions')),
      getJSON(withSource('/api/stats/items')),
    ]);
    if (generation !== loadGeneration) return;

    renderChampions(champions);
    renderRoles(roles);
    renderMatches(matches);
    renderChampionPerformance(championPerf);
    renderItemPerformance(itemPerf);
    await loadTimeline();
  } catch (error) {
    if (generation !== loadGeneration) return;
    $('#matches').innerHTML =
      `<tr><td colspan="8" class="error">Could not reach the API: ${escapeHtml(error.message)}</td></tr>`;
  }
}

async function refreshSyncStatus() {
  const status = $('#sync-status');
  const button = $('#sync-button');
  try {
    const info = await getJSON('/api/sync/status');
    if (info.configured) {
      status.textContent = `Ready — pulls your latest matches from Riot (${info.region}).`;
      button.disabled = false;
    } else {
      status.textContent =
        'Not configured yet — add RIOT_API_KEY and RIOT_ID in your project secrets, then reload.';
      button.disabled = true;
    }
  } catch (error) {
    status.textContent = `Could not read sync status: ${error.message}`;
    button.disabled = true;
  }
}

async function runSync() {
  const button = $('#sync-button');
  const status = $('#sync-status');
  button.disabled = true;
  status.textContent = 'Syncing from Riot…';
  try {
    const response = await fetch('/api/sync/riot?count=20', { method: 'POST' });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `Sync failed (${response.status})`);
    status.textContent = body.synced
      ? `Synced ${body.synced} new match${body.synced === 1 ? '' : 'es'} (${body.skipped} already stored).`
      : `Up to date — ${body.skipped} matches were already stored.`;
    await loadAll();
  } catch (error) {
    status.textContent = `Sync failed: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

$('#sync-button').addEventListener('click', runSync);
$('#source-filter').addEventListener('change', (event) => {
  state.source = event.target.value;
  loadAll();
});
$('#trend-champion').addEventListener('change', loadTimeline);

refreshSyncStatus();
loadAll();
