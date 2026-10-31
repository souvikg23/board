/* Board — offline lecture board. No dependencies, no build step.
   Security rule: lecture text and backup files are untrusted input.
   Everything from them is escaped before it reaches the page, and the page's
   Content-Security-Policy blocks inline scripts as a second line of defence. */
'use strict';
const $ = id => document.getElementById(id);

/* ── Inline formatting ─────────────────────────────────────── */
const esc = t => String(t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rich = t => esc(t)
  .replace(/\{\{(.+?)\|(.+?)\}\}/g, '<span class="fr"><span>$1</span><span>$2</span></span>')
  .replace(/\^\{(.+?)\}/g, '<sup>$1</sup>').replace(/_\{(.+?)\}/g, '<sub>$1</sub>')
  .replace(/~~(.+?)~~/g, '<span class="x">$1</span>');
/* matrices are split before escaping, so "&lt;" etc. can't be cut at its ";" */
const inl = t => t.split(/\[\[(.+?)\]\]/).map((p, k) => k % 2
  ? '<span class="mx"><table>' + p.split(';').map(r => '<tr>' +
      r.trim().split(/\s*,\s*|\s+/).filter(Boolean).map(c => '<td>' + rich(c) + '</td>').join('') +
    '</tr>').join('') + '</table></span>'
  : rich(p)).join('');
const fmt = t => { const [m, ...w] = t.split('||');
  return inl(m.trim()) + (w.length ? `<span class="why">${inl(w.join('||').trim())}</span>` : ''); };
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const nameOf = txt => (txt.match(/^#\s*(.+)$/m)?.[1] || 'Untitled').trim().slice(0, 60);

/* ── Parser ────────────────────────────────────────────────── */
function parse(txt) {
  const L = {time: 30, slides: []}; let cur = null;
  for (const raw of txt.split(/\r?\n/)) {
    const l = raw.trim(); if (!l) continue;
    const tm = l.match(/^time:\s*(\d+)\s*$/i);
    if (tm && !L.slides.length) { L.time = +tm[1]; continue; }
    if (l[0] === '#') { cur = {t: fmt(l.replace(/^#+\s*/, '')), s: '', st: []}; L.slides.push(cur); continue; }
    if (!cur) { cur = {t: '', s: '', st: []}; L.slides.push(cur); }
    const r = l.slice(1).trim();
    if (l[0] === '>') cur.s = r;
    else if (l[0] === '?') cur.st.push(['q', fmt(r)]);
    else if (l[0] === '!') cur.st.push(['key', fmt(r)]);
    else if (l[0] === '~' && l[1] !== '~') cur.st.push(['note', fmt(r)]);
    else cur.st.push(['line', fmt(l.replace(/^-\s+/, ''))]);
  }
  if (!L.slides.length) L.slides.push({t: 'Empty board', s: 'Press Edit to start writing', st: []});
  return L;
}

const STARTER = `time: 50

# Welcome to Board
> Press Space, or Next line, to reveal
? What happens when you press Next line?
Each line appears one at a time
The newest line is highlighted || older lines fade back
! Boxed lines hold the key result
~ Notes appear in small blue text.

# Pen and clock
> Draw over any slide
Turn the pen on with D, or the Pen button
Ink stays on its own slide || Clear ink wipes it
The clock turns red when your lecture time is up

# Your turn
> Press Edit to see how this was written
Slides, questions, notes and key lines are plain text
Maths works too: x^{2} + y^{2}, a_{n}, {{1|2}}
[[1, 0; 0, 1]] || a matrix
~~Wrong step~~ crossed out, then corrected
! Replace this text with your own lecture`;

/* ── Storage (this device only) ────────────────────────────── */
const Store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }
};
/* Anything read from storage or a backup file goes through clean(): wrong types are dropped,
   ids are forced to a safe alphabet. */
const clean = l => l && typeof l.content === 'string' ? {
  id: /^[a-z0-9]{1,24}$/i.test(l.id) ? l.id : uid(),
  name: typeof l.name === 'string' && l.name.trim() ? l.name.trim().slice(0, 80) : nameOf(l.content),
  content: l.content,
  modified: Number.isFinite(l.modified) ? l.modified : Date.now()
} : null;

function loadLibrary() {
  const s = Store.get('board.library') || {};
  const lectures = (Array.isArray(s.lectures) ? s.lectures : []).map(clean).filter(Boolean);
  if (!lectures.length) lectures.push({id: uid(), name: 'Welcome', content: STARTER, modified: Date.now()});
  return {lectures, activeId: lectures.some(l => l.id === s.activeId) ? s.activeId : lectures[0].id};
}
const FSTEPS = [0.75, 0.875, 1, 1.25, 1.5];   // text size steps; default is index 2 (100%)
function loadPrefs() {
  const p = Store.get('board.prefs') || {};
  return {theme: p.theme === 'light' ? 'light' : 'dark', fontLevel: FSTEPS[p.fontLevel] && Number.isInteger(p.fontLevel) ? p.fontLevel : 2};
}
let LIBRARY = loadLibrary(), PREFS = loadPrefs(), LEC;
const find = id => LIBRARY.lectures.find(l => l.id === id);
const active = () => find(LIBRARY.activeId) || LIBRARY.lectures[0];
const saveLibrary = () => Store.set('board.library', LIBRARY);
const savePrefs = () => Store.set('board.prefs', PREFS);

/* show a lecture from the top with a clean board */
function show(content) {
  LEC = parse(content);
  Ink.strokes = {}; Ink.undone = {};
  B.i = 0; B.n = 0; B.render();
}

function download(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* ── Theme ─────────────────────────────────────────────────── */
const Theme = {
  apply() {
    const dark = PREFS.theme === 'dark', b = $('theme-btn');
    document.documentElement.dataset.theme = PREFS.theme;
    document.querySelector('meta[name="theme-color"]').content = dark ? '#1F2B26' : '#F5F3EE';
    b.textContent = dark ? '☀️ Light' : '🌙 Dark';
    b.title = dark ? 'Switch to whiteboard' : 'Switch to chalkboard';
    Ink._updateBtns();
  },
  toggle() { PREFS.theme = PREFS.theme === 'dark' ? 'light' : 'dark'; savePrefs(); this.apply(); }
};

/* ── Font size ─────────────────────────────────────────────── */
const Font = {
  step(d) { PREFS.fontLevel = Math.max(0, Math.min(FSTEPS.length - 1, PREFS.fontLevel + d)); savePrefs(); this._apply(); },
  up() { this.step(1); },
  down() { this.step(-1); },
  _apply() {
    const s = FSTEPS[PREFS.fontLevel];
    document.documentElement.style.setProperty('--scale', s);
    $('font-level').textContent = Math.round(s * 100) + '%';
  }
};

/* ── Editor ────────────────────────────────────────────────── */
const Ed = {
  open() { $('src').value = active().content; $('editor').classList.remove('hidden'); $('src').focus(); this.stat(); },
  close() {
    $('editor').classList.add('hidden');
    const v = $('src').value, lec = active();
    if (v === lec.content) return B.render();
    Object.assign(lec, {content: v, name: nameOf(v), modified: Date.now()});
    saveLibrary(); show(v);
  },
  stat() {
    const n = parse($('src').value).slides.length;
    $('stat').textContent = `${n} slide${n === 1 ? '' : 's'} · saved on this device`;
  },
  save() {
    const v = $('src').value;
    download(new Blob([v], {type: 'text/plain'}), (nameOf(v).replace(/[^\w\- ]+/g, '').trim() || 'lecture') + '.txt');
  },
  pickFile() { $('file').click(); },
  load(inp) {
    const f = inp.files[0]; inp.value = ''; if (!f) return;
    f.text().then(t => { $('src').value = t; this.stat(); });
  }
};

/* ── Library ───────────────────────────────────────────────── */
const Lib = {
  open() { $('library').classList.remove('hidden'); this._render(); },
  close() { $('library').classList.add('hidden'); },
  _render() {
    $('lib-list').innerHTML = [...LIBRARY.lectures].sort((a, b) => b.modified - a.modified).map(l => {
      const n = parse(l.content).slides.length, id = esc(l.id);
      const d = new Date(l.modified).toLocaleDateString(undefined, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
      return `<div class="lib-item${l.id === LIBRARY.activeId ? ' active' : ''}" data-do="Lib.select" data-arg="${id}">
        <div class="lib-name" title="${esc(l.name)}">${esc(l.name)}</div>
        <div class="lib-meta">${n} slide${n === 1 ? '' : 's'} · ${d}</div>
        <div class="lib-actions">
          <button data-do="Lib.rename" data-arg="${id}" title="Rename">✏️</button>
          <button data-do="Lib.remove" data-arg="${id}" title="Delete">🗑️</button>
        </div>
      </div>`;
    }).join('');
  },
  select(id) {
    if (!find(id)) return;
    LIBRARY.activeId = id; saveLibrary();
    show(active().content); this._render();
  },
  add(lec) { LIBRARY.lectures.push(lec); this.select(lec.id); },
  create() { this.add({id: uid(), name: 'Untitled', content: '# New Lecture\n> Start writing here\n', modified: Date.now()}); },
  duplicate() { const c = active(); this.add({...c, id: uid(), name: c.name + ' (copy)', modified: Date.now()}); },
  rename(id) {
    const l = find(id), name = l && prompt('Lecture name', l.name)?.trim();
    if (!name) return;
    Object.assign(l, {name: name.slice(0, 80), modified: Date.now()});
    saveLibrary(); this._render();
  },
  remove(id) {
    const l = find(id); if (!l) return;
    if (LIBRARY.lectures.length === 1) return alert('Cannot delete the only lecture.');
    if (!confirm(`Delete "${l.name}"?`)) return;
    LIBRARY.lectures = LIBRARY.lectures.filter(x => x !== l);
    if (LIBRARY.activeId === id) return this.select(LIBRARY.lectures[0].id);
    saveLibrary(); this._render();
  },
  exportAll() {
    download(new Blob([JSON.stringify(LIBRARY, null, 2)], {type: 'application/json'}),
      'board-backup-' + new Date().toISOString().slice(0, 10) + '.json');
  },
  pickFile() { $('lib-import').click(); },
  importAll(inp) {
    const f = inp.files[0]; inp.value = ''; if (!f) return;
    f.text().then(t => {
      const data = JSON.parse(t);
      const lecs = (Array.isArray(data?.lectures) ? data.lectures : []).map(clean).filter(Boolean);
      if (!lecs.length) throw new Error('no lectures found in file');
      const fresh = lecs.filter(l => !find(l.id));
      if (fresh.length) LIBRARY.lectures.push(...fresh);
      else if (confirm(`All ${lecs.length} lecture(s) already exist. Replace entire library?`)) LIBRARY.lectures = lecs;
      else return;
      this.select(find(LIBRARY.activeId) ? LIBRARY.activeId : LIBRARY.lectures[0].id);
      alert(`Restored ${fresh.length || lecs.length} lecture(s).`);
    }).catch(e => alert('Could not read backup: ' + e.message));
  }
};

/* ── Board: slides and lines ───────────────────────────────── */
const B = {i: 0, n: 0,
  render() {
    const S = LEC.slides[this.i], N = S.st.length;
    $('title').innerHTML = S.t;
    $('sub').textContent = S.s;
    $('steps').innerHTML = S.st.map(([c, h], j) =>
      `<div class="step ${c}${j < this.n ? '' : ' hidden'}${j === this.n - 1 ? ' latest' : ''}">${h}</div>`).join('');
    $('count').textContent = `Line ${this.n} / ${N}`;
    $('nav').innerHTML = LEC.slides.map((s, j) =>
      `<li class="${j === this.i ? 'cur' : ''}" data-do="B.go" data-arg="${j}">${s.t.split(' · ')[0]}</li>`).join('');
    $('prog-fill').style.width = (N ? Math.round(this.n / N * 100) : 100) + '%';
    Ink.redraw();
  },
  next() {
    if (this.n < LEC.slides[this.i].st.length) this.n++;
    else if (this.i < LEC.slides.length - 1) { this.i++; this.n = 0; }
    this.render();
  },
  prev() {
    if (this.n > 0) this.n--;
    else if (this.i > 0) { this.i--; this.n = LEC.slides[this.i].st.length; }
    this.render();
  },
  go(j) { j = +j; if (!(j >= 0 && j < LEC.slides.length)) return; this.i = j; this.n = 0; this.render(); },
  seek(_, e) {
    const r = $('progress').getBoundingClientRect();
    this.n = Math.round(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * LEC.slides[this.i].st.length);
    this.render();
  },
  fullscreen() {
    (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.())?.catch(() => {});
  }
};

/* ── Clock ─────────────────────────────────────────────────── */
const Wake = {l: null,
  async on() { try { this.l = await navigator.wakeLock?.request('screen'); } catch {} },
  off() { this.l?.release(); this.l = null; }
};
const Clock = {t0: null, acc: 0, h: null,
  toggle() {
    if (this.h) { this.acc += Date.now() - this.t0; clearInterval(this.h); this.h = null; Wake.off(); }
    else { this.t0 = Date.now(); this.h = setInterval(() => this.show(), 500); Wake.on(); }
    $('tbtn').textContent = this.h ? 'Pause clock' : 'Resume clock';
  },
  show() {
    const s = Math.floor((this.acc + (this.h ? Date.now() - this.t0 : 0)) / 1000), el = $('clock');
    el.textContent = String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
    el.style.color = s >= LEC.time * 60 ? 'var(--cancel)' : '';
  }
};
document.addEventListener('visibilitychange', () => { if (!document.hidden && Clock.h) Wake.on(); });

/* ── Ink: pen, duster, undo/redo ───────────────────────────── */
const PALETTE = {dark: ['#F2D16B', '#ECEAE2', '#8EC5E8', '#F29E9E'], light: ['#B8860B', '#1F2B26', '#2171A5', '#C0392B']};
const Ink = {on: false, mode: 'pen', ci: 0, strokes: {}, undone: {}, cur: null, cv: null,
  get col() { return PALETTE[PREFS.theme][this.ci]; },
  init() {
    this.cv = $('ink');
    const pg = $('page'), pos = e => { const r = this.cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    new ResizeObserver(() => {
      const d = devicePixelRatio || 1;
      this.cv.width = Math.round(pg.offsetWidth * d); this.cv.height = Math.round(pg.offsetHeight * d);
      this.redraw();
    }).observe(pg);
    this.cv.addEventListener('pointerdown', e => {
      if (!this.on) return;
      this.cur = this.mode === 'duster' ? {e: true, p: [pos(e)]} : {c: this.col, p: [pos(e)]};
      (this.strokes[B.i] ??= []).push(this.cur);
      this.undone[B.i] = [];                       // a new stroke clears redo
      this.cv.setPointerCapture(e.pointerId);
    });
    this.cv.addEventListener('pointermove', e => { if (this.cur) { this.cur.p.push(pos(e)); this.redraw(); } });
    for (const t of ['pointerup', 'pointercancel']) this.cv.addEventListener(t, () => { this.cur = null; });
  },
  /* one place that makes buttons, swatches and canvas match the state */
  _updateBtns() {
    const pen = this.on && this.mode === 'pen', duster = this.on && this.mode === 'duster';
    this.cv.classList.toggle('on', this.on);
    this.cv.classList.toggle('duster', duster);
    $('pen').textContent = pen ? 'Pen on' : 'Pen off';
    $('pen').classList.toggle('on', pen);
    $('duster').classList.toggle('on', duster);
    $('sws').innerHTML = PALETTE[PREFS.theme].map((c, i) =>
      `<span class="sw${i === this.ci ? ' sel' : ''}" style="background:${c}" data-do="Ink.pick" data-arg="${i}" title="pen colour"></span>`).join('');
  },
  pick(i) { this.ci = +i; this.on = true; this.mode = 'pen'; this._updateBtns(); },
  toggle() { this.on = !this.on; this.mode = 'pen'; this._updateBtns(); },
  toggleDuster() { this.mode = this.on && this.mode === 'duster' ? 'pen' : 'duster'; this.on = true; this._updateBtns(); },
  _move(from, to) { const s = from[B.i]?.pop(); if (s) { (to[B.i] ??= []).push(s); this.redraw(); } },
  undo() { this._move(this.strokes, this.undone); },
  redo() { this._move(this.undone, this.strokes); },
  clear() { this.strokes[B.i] = []; this.undone[B.i] = []; this.redraw(); },
  redraw() {
    const g = this.cv?.getContext('2d'), d = devicePixelRatio || 1;
    if (!g) return;
    g.setTransform(d, 0, 0, d, 0, 0);
    g.clearRect(0, 0, this.cv.width, this.cv.height);
    g.lineCap = g.lineJoin = 'round';
    for (const s of this.strokes[B.i] || []) {
      g.globalCompositeOperation = s.e ? 'destination-out' : 'source-over';   // duster erases pixels
      g.lineWidth = s.e ? 36 : 3;
      g.strokeStyle = s.e ? '#000' : s.c;
      g.beginPath();
      s.p.forEach(([x, y], j) => j ? g.lineTo(x, y) : g.moveTo(x, y));
      g.stroke();
    }
    g.globalCompositeOperation = 'source-over';
  }
};

/* ── Buttons and keys ──────────────────────────────────────── */
/* Buttons carry data-do="Object.method" (and optional data-arg); no inline handlers,
   so the page can forbid inline script entirely. */
const ACTIONS = {B, Ed, Lib, Ink, Clock, Theme, Font};
const run = (act, arg, e) => { const [o, m] = act.split('.'); ACTIONS[o]?.[m]?.(arg, e); };
document.addEventListener('click', e => { const el = e.target.closest('[data-do]'); if (el) run(el.dataset.do, el.dataset.arg, e); });
$('file').addEventListener('change', e => Ed.load(e.target));
$('lib-import').addEventListener('change', e => Lib.importAll(e.target));
$('src').addEventListener('input', () => Ed.stat());

const KEYS = {' ': 'B.next', arrowright: 'B.next', pagedown: 'B.next', arrowleft: 'B.prev', pageup: 'B.prev',
  e: 'Ed.open', l: 'Lib.open', d: 'Ink.toggle', x: 'Ink.toggleDuster', c: 'Ink.clear', t: 'Clock.toggle',
  w: 'Theme.toggle', '=': 'Font.up', '+': 'Font.up', '-': 'Font.down', _: 'Font.down', f: 'B.fullscreen'};
document.addEventListener('keydown', e => {
  const overlay = ['editor', 'library'].find(id => !$(id).classList.contains('hidden'));
  if (overlay) { if (e.key === 'Escape') (overlay === 'editor' ? Ed : Lib).close(); return; }
  const k = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); return e.shiftKey ? Ink.redo() : Ink.undo(); }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (/^[1-9]$/.test(k)) return B.go(k - 1);
  if (KEYS[k]) { e.preventDefault(); run(KEYS[k]); }
});

/* ── Start ─────────────────────────────────────────────────── */
Ink.init();
Theme.apply();
Font._apply();
show(active().content);
if ('serviceWorker' in navigator && location.protocol !== 'file:') navigator.serviceWorker.register('sw.js');
