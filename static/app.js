/* lolzin-api landing page: sync trigger + performance views. */

const $ = (selector) => document.querySelector(selector);
const state = { source: '' };

const escapeHtml = (value) =>
  String(value ?? '').replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const orDash = (value) =>
  (value === null || value === undefined || value === '') ? '—' : escapeHtml(value);

/* A plain YYYY-MM-DD is a calendar date; parse it as local so the label never
   drifts a day backwards in negative-offset timezones. */
const shortDate = (value) => {
  const iso = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? `${value}T00:00:00`
    : value;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

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

/* Multi-series weekly win-rate chart for the most-played champions. */
const TREND_COLORS = ['#c8aa6e', '#0ac8b9', '#4a9eff', '#e0605e', '#a06bff'];

function renderChampionTrends(series) {
  const host = $('#champion-trends');
  const legend = $('#champion-trends-legend');
  const drawn = (series || []).filter((s) => s.points.length);

  if (!drawn.length) {
    host.innerHTML = '<p class="empty">No matches in this window yet.</p>';
    legend.innerHTML = '';
    return;
  }

  const periods = [...new Set(drawn.flatMap((s) => s.points.map((p) => p.period)))].sort();
  const W = 720;
  const H = 240;
  const pad = { top: 16, right: 18, bottom: 34, left: 48 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;
  const xAt = (period) => periods.length === 1
    ? pad.left + plotW / 2
    : pad.left + (periods.indexOf(period) / (periods.length - 1)) * plotW;
  const yAt = (rate) => pad.top + (1 - Math.min(100, Math.max(0, rate)) / 100) * plotH;
  const colorAt = (index) => TREND_COLORS[index % TREND_COLORS.length];

  const grid = [0, 25, 50, 75, 100].map((rate) => `
    <line class="chart-grid" x1="${pad.left}" y1="${yAt(rate)}" x2="${W - pad.right}" y2="${yAt(rate)}"></line>
    <text class="chart-axis" x="${pad.left - 10}" y="${yAt(rate) + 4}" text-anchor="end">${rate}%</text>
  `).join('');

  const xLabels = periods.map((period) => `
    <text class="chart-axis" x="${xAt(period)}" y="${H - pad.bottom + 20}" text-anchor="middle">${shortDate(period)}</text>
  `).join('');

  const lines = drawn.map((s, index) => {
    const color = colorAt(index);
    const points = s.points.map((p) => `${xAt(p.period)},${yAt(p.win_rate)}`).join(' ');
    const dots = s.points.map((p) => `
      <circle class="chart-dot" cx="${xAt(p.period)}" cy="${yAt(p.win_rate)}" r="4" fill="${color}">
        <title>${escapeHtml(s.name)} · ${shortDate(p.period)} · ${p.win_rate}% (${p.games} games)</title>
      </circle>
    `).join('');
    return `<polyline class="chart-line" points="${points}" fill="none" stroke="${color}"></polyline>${dots}`;
  }).join('');

  host.innerHTML = `
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Weekly win rate for the most-played champions">
      ${grid}
      ${xLabels}
      ${lines}
    </svg>
  `;

  legend.innerHTML = drawn.map((s, index) => `
    <span class="legend-item">
      <i class="legend-swatch" style="background:${colorAt(index)}"></i>
      ${escapeHtml(s.name)}
      <span class="legend-meta">${s.games} game${s.games === 1 ? '' : 's'}</span>
    </span>
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

  // Win-rate trend for the most-played champions over the last 8 weeks.
  const trendParams = new URLSearchParams({ weeks: '8', limit: '5' });
  if (state.source) trendParams.set('source', state.source);

  try {
    const [champions, roles, matches, championPerf, itemPerf, championTrends] =
      await Promise.all([
        getJSON('/api/champions?limit=200'),
        getJSON('/api/stats/roles'),
        getJSON(`/api/matches?${matchParams}`),
        getJSON(withSource('/api/stats/champions')),
        getJSON(withSource('/api/stats/items')),
        getJSON(`/api/stats/trends/champions?${trendParams}`),
      ]);
    if (generation !== loadGeneration) return;

    renderChampions(champions);
    renderRoles(roles);
    renderMatches(matches);
    renderChampionPerformance(championPerf);
    renderItemPerformance(itemPerf);
    renderChampionTrends(championTrends);
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
