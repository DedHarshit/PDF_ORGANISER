// ── API base ───────────────────────────────────────────────────────────
const API = 'http://localhost:5000/api';

// ── Theme (dark mode) ───────────────────────────────────────────────────
// Preference is client-only (localStorage), independent of the backend's
// .gui_config.json — it's a display setting, not an organiser setting.
const THEME_KEY = 'pdfOrganiser.theme';

function applyTheme(theme) {
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  const btn = document.getElementById('themeToggle');
  if (btn) btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
}

function getStoredTheme() {
  try {
    return localStorage.getItem(THEME_KEY);
  } catch {
    return null; // localStorage unavailable (privacy mode, etc.) — fall back to light
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    // Storage blocked — theme still applies for this session, just won't persist.
  }
}

// Apply the saved preference as early as possible (before other init work)
// so there's no flash of the wrong theme on load. Default is dark; users
// who explicitly choose light get that remembered via localStorage.
applyTheme(getStoredTheme() === 'light' ? 'light' : 'dark');

// ── Tab switching ──────────────────────────────────────────────────────
// Only one tab (Organise) remains — Settings and Logs were removed since
// every field they exposed already lives in Step 1–3 here, and kept falling
// out of sync with it). This is now a no-op kept
// only so the markup's onclick wiring doesn't need touching elsewhere.
function switchTab(name) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector('.nav-tab').classList.add('active');
}

// ── Toast ──────────────────────────────────────────────────────────────
function toast(msg, type='ok') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show ' + type;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.className = '', 3000);
}

// ── Console ──────────────────────────────────────────────────────────
function log(msg, cls='') {
  const con = document.getElementById('console');
  const now = new Date().toTimeString().slice(0,8);
  const line = document.createElement('div');
  line.innerHTML = `<span class="log-ts">${now}</span><span class="${cls}">${escHtml(msg)}</span>`;
  con.appendChild(line);
  con.scrollTop = con.scrollHeight;
}
function clearConsole() { document.getElementById('console').innerHTML = ''; }
function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ── Folder pickers ─────────────────────────────────────────────────────
function pickFolder(which) {
  document.getElementById(which + 'Input').click();
}
document.getElementById('srcInput').addEventListener('change', e => {
  if (e.target.files.length) setFolderPath('src', getFolderPath(e.target.files));
});
document.getElementById('dstInput').addEventListener('change', e => {
  if (e.target.files.length) setFolderPath('dst', getFolderPath(e.target.files));
});
function getFolderPath(files) {
  const rel = files[0].webkitRelativePath;
  return rel.split('/')[0];
}
function setFolderPath(which, path) {
  const el = document.getElementById(which + 'Path');
  el.textContent = path;
  el.classList.remove('empty');
  document.getElementById(which + 'Manual').value = path;
  checkStep1();
  saveFolderToApi(which, path);
}
function updatePathFromManual(which) {
  const val = document.getElementById(which + 'Manual').value.trim();
  const el  = document.getElementById(which + 'Path');
  if (val) { el.textContent = val; el.classList.remove('empty'); }
  else     { el.textContent = 'Click Browse to select…'; el.classList.add('empty'); }
  checkStep1();
  if (val) saveFolderToApi(which, val);
}
function saveFolderToApi(which, path) {
  const key = which === 'src' ? 'watch_dir' : 'output_dir';
  fetch(API + '/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({[key]: path}) }).catch(()=>{});
}
function checkStep1() {
  const src = document.getElementById('srcManual').value.trim();
  const dst = document.getElementById('dstManual').value.trim();
  document.getElementById('step1').classList.toggle('complete', !!(src && dst));
}

// ── Token ─────────────────────────────────────────────────────────────
function toggleTokenVis() {
  const inp = document.getElementById('tokenInput');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}
function markTokenStep() {
  const val = document.getElementById('tokenInput').value.trim();
  document.getElementById('step2').classList.toggle('complete', val.length > 10);
  updateTokenFormatHint(val);
  saveTokenToApi(val);
}
// Debounced so we don't fire a request on every keystroke — same persistence
// behaviour Step 1's folder fields already have, applied consistently here.
let _tokenSaveTimer = null;
function saveTokenToApi(token) {
  clearTimeout(_tokenSaveTimer);
  if (!token) return;
  _tokenSaveTimer = setTimeout(() => {
    fetch(API + '/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ github_token: token }) }).catch(()=>{});
  }, 600);
}
// Step 3 (Behaviour) always has valid defaults the moment the page loads,
// so it's marked complete on init and whenever its controls change —
// matching the same visual treatment Steps 1 and 2 get.
function markStep3() {
  document.getElementById('step3').classList.add('complete');
}
function updateTokenFormatHint(val) {
  const el = document.getElementById('tokenFormat');
  if (!val) { el.textContent = ''; el.className = 'token-format'; return; }
  const looksValid = /^(ghp_|github_pat_|gho_)/.test(val) && val.length >= 20;
  if (looksValid) {
    el.className = 'token-format valid';
    el.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><circle cx="6" cy="6" r="5"/><path d="M3.8 6.2l1.5 1.5 2.7-3"/></svg>Looks like a valid GitHub token format';
  } else {
    el.className = 'token-format invalid';
    el.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M6 1l5 9.5H1L6 1z"/><path d="M6 4.8v2.4M6 8.6v.4"/></svg>Doesn\'t match a known GitHub token prefix (ghp_, github_pat_, gho_)';
  }
}

// ── Watcher toggle ─────────────────────────────────────────────────────
let _watcherES = null;

async function toggleWatcher(on) {
  try {
    if (on) {
      // 1. Save current config (token + folders) before starting
      const token = document.getElementById('tokenInput').value.trim();
      const src   = document.getElementById('srcManual').value.trim();
      const dst   = document.getElementById('dstManual').value.trim();
      if (!src || !dst)   { toast('Set source and destination folders first', 'err'); document.getElementById('autoWatcher').checked = false; return; }
      if (!token)         { toast('Enter your GitHub token first', 'err');            document.getElementById('autoWatcher').checked = false; return; }
      await fetch(API + '/config', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ watch_dir: src, output_dir: dst, github_token: token })
      });

      // 2. Start sweep (process existing files) — stream its progress into console
      log('Watcher: sweeping existing files first…', 'log-ok');
      await new Promise(resolve => {
        const sweepES = new EventSource(API + '/watcher/sweep');
        sweepES.onmessage = e => {
          const d = JSON.parse(e.data);
          if (d.type === 'start')    { log(`Watcher sweep: ${d.total} file(s) found.`); }
          if (d.type === 'progress') { log(d.msg, d.status === 'ok' ? 'log-ok' : 'log-err'); updateTableRow(d); updateStats(d); }
          if (d.type === 'done')     { sweepES.close(); log(`Watcher sweep done — ${d.sorted} sorted, ${d.errors} errors.`, 'log-ok'); resolve(); }
          if (d.type === 'error')    { sweepES.close(); log(d.message || 'Sweep error', 'log-err'); resolve(); }
        };
        sweepES.onerror = () => { sweepES.close(); resolve(); };
      });

      // 3. Start background observer for NEW files
      const r = await fetch(API + '/watcher/start', { method: 'POST' });
      const d = await r.json();
      if (d.error) { toast(d.error, 'err'); document.getElementById('autoWatcher').checked = false; return; }
      updateWatcherBadge(true);
      toast('Watcher active — monitoring for new PDFs', 'ok');
      log('Watcher started. Drop PDFs into source folder to auto-sort them.', 'log-ok');

      // 4. Open SSE stream for live events from the observer
      if (_watcherES) _watcherES.close();
      _watcherES = new EventSource(API + '/watcher/events');
      _watcherES.onmessage = e => {
        const d = JSON.parse(e.data);
        if (d.type === 'connected') {
          log('Watcher event stream connected — drop PDFs into source folder to auto-sort.', 'log-ok');
          return;
        }
        if (d.type === 'heartbeat') return; // silent keepalive
        if (d.type === 'file') {
          log(d.msg, d.status === 'ok' ? 'log-ok' : 'log-err');
          toast(d.status === 'ok' ? `Sorted: ${d.file}` : `Error: ${d.file}`, d.status === 'ok' ? 'ok' : 'err');
          // Add new row to table or update existing
          const existing = document.getElementById('badge-' + d.file);
          if (!existing) {
            const wrap = document.getElementById('fileTableWrap');
            if (!document.getElementById('fileTableBody')) {
              wrap.innerHTML = `
                <div class="file-table-scroll">
                  <table class="file-table">
                    <thead><tr><th>File</th><th>Size</th><th>Destination</th><th>Status</th></tr></thead>
                    <tbody id="fileTableBody"></tbody>
                  </table>
                </div>`;
            }
            wrap.style.display = 'block';
            const body = document.getElementById('fileTableBody');
            const row = document.createElement('tr');
            row.id = 'row-' + d.file;
            row.innerHTML = `
              <td class="file-name" title="${escHtml(d.file)}">${escHtml(d.file)}</td>
              <td class="file-size">—</td>
              <td class="file-dest" id="dest-${escHtml(d.file)}" title="${escHtml(d.dest || '')}">${escHtml(d.dest || '—')}</td>
              <td><span class="file-status-badge ${d.status === 'ok' ? 'badge-ok' : 'badge-error'}" id="badge-${escHtml(d.file)}">${d.status === 'ok' ? 'Done' : 'Error'}</span></td>`;
            body.prepend(row);
          } else {
            updateTableRow(d);
          }
          // Bump stats
          const sorted = (parseInt(document.getElementById('statSorted').textContent) || 0) + (d.status === 'ok' ? 1 : 0);
          const errors = (parseInt(document.getElementById('statErrors').textContent) || 0) + (d.status !== 'ok' ? 1 : 0);
          const total  = (parseInt(document.getElementById('statTotal').textContent)  || 0) + 1;
          document.getElementById('statSorted').textContent = sorted;
          document.getElementById('statErrors').textContent = errors;
          document.getElementById('statTotal').textContent  = total;
        }
        if (d.type === 'stopped') {
          _watcherES.close(); _watcherES = null;
          updateWatcherBadge(false);
          document.getElementById('autoWatcher').checked = false;
          log('Watcher stopped.', 'log-warn');
        }
      };
      _watcherES.onerror = () => {
        // SSE will auto-reconnect; log it so the user can see transient drops
        log('Watcher stream reconnecting…', 'log-warn');
      };

    } else {
      // Stop watcher
      if (_watcherES) { _watcherES.close(); _watcherES = null; }
      const r = await fetch(API + '/watcher/stop', { method: 'POST' });
      const d = await r.json();
      updateWatcherBadge(false);
      toast(d.message, 'ok');
      log('Watcher stopped.', 'log-warn');
    }
  } catch(err) {
    toast('API not reachable — is api.py running?', 'err');
    document.getElementById('autoWatcher').checked = false;
  }
}

// Helper: update a file table row after processing
function updateTableRow(d) {
  const badge = document.getElementById('badge-' + d.file);
  const dest  = document.getElementById('dest-'  + d.file);
  if (badge) {
    badge.className  = 'file-status-badge ' + (d.status === 'ok' ? 'badge-ok' : 'badge-error');
    badge.textContent = d.status === 'ok' ? 'Done' : 'Error';
  }
  if (dest && d.dest) {
    dest.textContent = d.dest;
    dest.title = d.dest; // keep tooltip in sync with truncated text
  }
}

// Helper: update stats counters during sweep
function updateStats(d) {
  const sorted = parseInt(document.getElementById('statSorted').textContent) || 0;
  const errors = parseInt(document.getElementById('statErrors').textContent) || 0;
  if (d.status === 'ok') document.getElementById('statSorted').textContent = sorted + 1;
  else                   document.getElementById('statErrors').textContent = errors + 1;
  document.getElementById('statPending').textContent = Math.max(0,
    (parseInt(document.getElementById('statTotal').textContent) || 0) - d.index);
}
function updateWatcherBadge(active) {
  const badge = document.getElementById('watcherBadge');
  const lbl   = document.getElementById('watcherLabel');
  badge.classList.toggle('active', active);
  lbl.textContent = active ? 'Watching…' : 'Watcher off';
}

// ── Scan files ─────────────────────────────────────────────────────────
let scannedFiles = [];
async function scanFiles() {
  try {
    const r = await fetch(API + '/scan');
    const d = await r.json();
    scannedFiles = d.files || [];
    renderFileTable(scannedFiles);
    document.getElementById('statTotal').textContent   = d.count || 0;
    document.getElementById('statPending').textContent = d.count || 0;
    document.getElementById('statSorted').textContent  = 0;
    document.getElementById('statErrors').textContent  = 0;
    document.getElementById('step3').classList.add('complete');
    log(`Scan complete: ${d.count} PDF(s) found.`, 'log-ok');
  } catch {
    toast('Could not reach backend. Is api.py running?', 'err');
    log('Backend unreachable. Start api.py first.', 'log-err');
  }
}

function renderFileTable(files) {
  const wrap = document.getElementById('fileTableWrap');
  const body = document.getElementById('fileTableBody');
  if (!files.length) {
    wrap.style.display = 'block';
    wrap.innerHTML = `
      <div class="empty-state">
        <svg width="34" height="34" viewBox="0 0 34 34" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M5 9h24v18a2 2 0 01-2 2H7a2 2 0 01-2-2V9z"/><path d="M5 9l3.5-5h17L29 9"/><path d="M12 17h10M12 21h6"/></svg>
        <div class="empty-state-title">No PDFs in the source folder</div>
        <div class="empty-state-sub">Drop a few files into your inbox folder, then scan again.</div>
      </div>`;
    return;
  }
  
  if (!document.getElementById('fileTableBody')) {
    wrap.innerHTML = `
      <div class="file-table-scroll">
        <table class="file-table">
          <thead><tr><th>File</th><th>Size</th><th>Destination</th><th>Status</th></tr></thead>
          <tbody id="fileTableBody"></tbody>
        </table>
      </div>`;
  }
  wrap.style.display = 'block';
  document.getElementById('fileTableBody').innerHTML = files.map(f => `
    <tr id="row-${escHtml(f.name)}">
      <td class="file-name" title="${escHtml(f.name)}">${escHtml(f.name)}</td>
      <td class="file-size">${fmt(f.size)}</td>
      <td class="file-dest" id="dest-${escHtml(f.name)}" title="">—</td>
      <td><span class="file-status-badge badge-pending" id="badge-${escHtml(f.name)}">Pending</span></td>
    </tr>`).join('');
}
function fmt(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/1048576).toFixed(1) + ' MB';
}

// ── Run ────────────────────────────────────────────────────────────────
let running = false;
async function startRun() {
  if (running) return;

  // Save current form values to API
  const token = document.getElementById('tokenInput').value.trim();
  const src   = document.getElementById('srcManual').value.trim();
  const dst   = document.getElementById('dstManual').value.trim();
  if (!src)   { toast('Set a source folder first', 'err'); return; }
  if (!dst)   { toast('Set a destination folder first', 'err'); return; }
  if (!token) { toast('Enter your GitHub token first', 'err'); return; }

  try {
    await fetch(API + '/config', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        watch_dir: src, output_dir: dst, github_token: token,
        file_action: document.getElementById('fileAction').value,
        log_level:   document.getElementById('logLevel').value,
        skip_dupes:  document.getElementById('skipDupes').checked,
        auto_mkdir:  document.getElementById('autoMkdir').checked,
      })
    });
  } catch {
    toast('Cannot reach api.py — start the backend first!', 'err');
    return;
  }

  // Scan first to populate table
  await scanFiles();
  if (!scannedFiles.length) { toast('No PDFs found in source folder', 'err'); return; }

  running = true;
  document.getElementById('runBtn').disabled  = true;
  document.getElementById('runBtn2').disabled = true;
  document.getElementById('progressWrap').style.display = 'block';

  let sorted = 0, errors = 0, total = scannedFiles.length;

  const es = new EventSource(API + '/run');
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'start') {
      total = d.total;
      log(`Starting run — ${total} file(s) to process.`);
    }
    if (d.type === 'progress') {
      const pct = Math.round((d.index / d.total) * 100);
      document.getElementById('progressFill').style.width  = pct + '%';
      document.getElementById('progressPct').textContent   = pct + '%';
      document.getElementById('progressLabel').textContent = `Processing ${d.index}/${d.total}…`;

      const cls = d.status === 'ok' ? 'log-ok' : 'log-err';
      log(d.msg, cls);

      // Update table row
      const badge = document.getElementById('badge-' + d.file);
      const dest  = document.getElementById('dest-' + d.file);
      if (badge) {
        badge.className = 'file-status-badge ' + (d.status === 'ok' ? 'badge-ok' : 'badge-error');
        badge.textContent = d.status === 'ok' ? 'Done' : 'Error';
      }
      if (dest && d.dest) { dest.textContent = d.dest; dest.title = d.dest; }

      if (d.status === 'ok') sorted++; else errors++;
      document.getElementById('statSorted').textContent  = sorted;
      document.getElementById('statErrors').textContent  = errors;
      document.getElementById('statPending').textContent = Math.max(0, total - d.index);
    }
    if (d.type === 'done') {
      es.close();
      running = false;
      document.getElementById('runBtn').disabled  = false;
      document.getElementById('runBtn2').disabled = false;
      document.getElementById('progressLabel').textContent = 'Complete!';
      document.getElementById('progressFill').style.width  = '100%';
      log(`Done — ${d.sorted} sorted, ${d.errors} errors.`, 'log-ok');
      toast(`Done! ${d.sorted} sorted, ${d.errors} errors.`, 'ok');
    }
    if (d.type === 'error') {
      es.close(); running = false;
      document.getElementById('runBtn').disabled  = false;
      document.getElementById('runBtn2').disabled = false;
      log(d.message || 'Unknown error', 'log-err');
      toast(d.message || 'Run failed', 'err');
    }
  };
  es.onerror = () => {
    if (!running) return;
    es.close(); running = false;
    document.getElementById('runBtn').disabled  = false;
    document.getElementById('runBtn2').disabled = false;
    log('Connection to backend lost.', 'log-err');
    toast('Backend connection lost', 'err');
  };
}

// ── Init: load config into form ────────────────────────────────────────
(async function init() {
  try {
    const r = await fetch(API + '/config');
    const d = await r.json();
    if (d.watch_dir)  { document.getElementById('srcManual').value = d.watch_dir;  document.getElementById('srcPath').textContent = d.watch_dir;  document.getElementById('srcPath').classList.remove('empty'); }
    if (d.output_dir) { document.getElementById('dstManual').value = d.output_dir; document.getElementById('dstPath').textContent = d.output_dir; document.getElementById('dstPath').classList.remove('empty'); }
    if (d.github_token) { document.getElementById('tokenInput').value = d.github_token; markTokenStep(); }
    if (d.file_action) document.getElementById('fileAction').value = d.file_action;
    if (d.log_level)   document.getElementById('logLevel').value   = d.log_level;
    document.getElementById('skipDupes').checked   = d.skip_dupes !== false;
    document.getElementById('autoMkdir').checked   = d.auto_mkdir !== false;
    checkStep1();
    markStep3();

    const sr = await fetch(API + '/status');
    const sd = await sr.json();
    if (sd.watcher_active) {
      // Backend watcher is already running (e.g. survived a page refresh) —
      // just reflect that state, don't start a second one.
      document.getElementById('autoWatcher').checked = true;
      updateWatcherBadge(true);
    } else if (d.auto_watcher) {
      // Saved preference says the watcher should be on, but the backend
      // process was restarted and it isn't actually running. Previously the
      // checkbox was set to ON here without starting anything, so the toggle
      // showed "on" while the badge said "Watcher off" (see screenshot).
      // Start it for real instead, so the UI doesn't lie about its state.
      document.getElementById('autoWatcher').checked = true;
      toggleWatcher(true);
    } else {
      document.getElementById('autoWatcher').checked = false;
    }
    if (sd.pdf_count > 0) {
      document.getElementById('statTotal').textContent   = sd.pdf_count;
      document.getElementById('statPending').textContent = sd.pdf_count;
    }
  } catch { /* backend not yet started */ }
})();
