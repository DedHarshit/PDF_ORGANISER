// ── API base ───────────────────────────────────────────────────────────
const API = 'http://localhost:5000/api';

// ── Tab switching ──────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  const tabs = ['organise','settings','logs'];
  document.querySelectorAll('.nav-tab')[tabs.indexOf(name)].classList.add('active');
  if (name === 'settings') loadSettings();
  if (name === 'logs') fetchLog();
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
  else     { el.textContent = 'Click to select folder…'; el.classList.add('empty'); }
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
function toggleCfgTokenVis() {
  const inp = document.getElementById('cfgToken');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}
function markTokenStep() {
  const val = document.getElementById('tokenInput').value.trim();
  document.getElementById('step2').classList.toggle('complete', val.length > 10);
}

// ── Watcher toggle ─────────────────────────────────────────────────────
async function toggleWatcher(on) {
  try {
    const ep = on ? '/watcher/start' : '/watcher/stop';
    const r  = await fetch(API + ep, { method: 'POST' });
    const d  = await r.json();
    if (d.error) { toast(d.error, 'err'); return; }
    updateWatcherBadge(on);
    toast(d.message, 'ok');
  } catch {
    toast('API not reachable — is api.py running?', 'err');
  }
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
  if (!files.length) { wrap.style.display = 'none'; return; }
  wrap.style.display = 'block';
  body.innerHTML = files.map(f => `
    <tr id="row-${escHtml(f.name)}">
      <td class="file-name">${escHtml(f.name)}</td>
      <td class="file-size">${fmt(f.size)}</td>
      <td id="dest-${escHtml(f.name)}" style="color:var(--muted);font-family:var(--font-mono);font-size:12px">—</td>
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
      if (dest && d.dest) dest.textContent = d.dest;

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

// ── Settings ───────────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const r = await fetch(API + '/config');
    const d = await r.json();
    document.getElementById('cfgSrc').value         = d.watch_dir  || '';
    document.getElementById('cfgDst').value         = d.output_dir || '';
    document.getElementById('cfgToken').value       = d.github_token || '';
    document.getElementById('cfgAction').value      = d.file_action  || 'move';
    document.getElementById('cfgLogLevel').value    = d.log_level    || 'INFO';
    document.getElementById('cfgAutoWatcher').checked = !!d.auto_watcher;
    document.getElementById('cfgSkipDupes').checked   = d.skip_dupes !== false;
  } catch { toast('Could not load config — is api.py running?', 'err'); }
}
async function saveSettings() {
  const cfg = {
    watch_dir:    document.getElementById('cfgSrc').value.trim(),
    output_dir:   document.getElementById('cfgDst').value.trim(),
    github_token: document.getElementById('cfgToken').value.trim(),
    file_action:  document.getElementById('cfgAction').value,
    log_level:    document.getElementById('cfgLogLevel').value,
    auto_watcher: document.getElementById('cfgAutoWatcher').checked,
    skip_dupes:   document.getElementById('cfgSkipDupes').checked,
  };
  try {
    await fetch(API + '/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cfg) });
    toast('Settings saved!', 'ok');
    // Also update organise tab
    if (cfg.watch_dir)    { document.getElementById('srcManual').value = cfg.watch_dir;  document.getElementById('srcPath').textContent = cfg.watch_dir;  document.getElementById('srcPath').classList.remove('empty'); }
    if (cfg.output_dir)   { document.getElementById('dstManual').value = cfg.output_dir; document.getElementById('dstPath').textContent = cfg.output_dir; document.getElementById('dstPath').classList.remove('empty'); }
    if (cfg.github_token) { document.getElementById('tokenInput').value = cfg.github_token; markTokenStep(); }
    checkStep1();
  } catch { toast('Save failed — is api.py running?', 'err'); }
}

// ── Log tab ────────────────────────────────────────────────────────────
let _autoRefresh = null;
async function fetchLog() {
  try {
    const r = await fetch(API + '/log?lines=200');
    const d = await r.json();
    const el = document.getElementById('logFull');
    el.innerHTML = d.lines.map(l => {
      let cls = '';
      if (l.includes('[ERROR]'))   cls = 'log-err';
      else if (l.includes('[WARNING]')) cls = 'log-warn';
      else if (l.includes('[INFO]'))    cls = 'log-ok';
      return `<div class="${cls}">${escHtml(l)}</div>`;
    }).join('') || '<span class="log-dim">Log is empty.</span>';
    el.scrollTop = el.scrollHeight;
  } catch { document.getElementById('logFull').innerHTML = '<span class="log-err">Cannot reach api.py</span>'; }
}
function toggleAutoRefresh() {
  const lbl = document.getElementById('autoRefreshLabel');
  if (_autoRefresh) {
    clearInterval(_autoRefresh); _autoRefresh = null;
    lbl.textContent = '▶ Auto-refresh';
  } else {
    _autoRefresh = setInterval(fetchLog, 3000);
    lbl.textContent = '⏸ Stop refresh';
    fetchLog();
  }
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
    document.getElementById('autoWatcher').checked = !!d.auto_watcher;
    document.getElementById('skipDupes').checked   = d.skip_dupes !== false;
    document.getElementById('autoMkdir').checked   = d.auto_mkdir !== false;
    checkStep1();

    const sr = await fetch(API + '/status');
    const sd = await sr.json();
    if (sd.watcher_active) updateWatcherBadge(true);
    if (sd.pdf_count > 0) {
      document.getElementById('statTotal').textContent   = sd.pdf_count;
      document.getElementById('statPending').textContent = sd.pdf_count;
    }
  } catch { /* backend not yet started */ }
})();
