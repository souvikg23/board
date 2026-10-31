/* Board — a blank teaching board. No dependencies, no build step, no network.
   Everything the user makes stays in this browser (localStorage).
   Security: nothing the user stores is ever put into the page as HTML; saved data is
   validated on load, and the page's Content-Security-Policy forbids inline script. */
'use strict';
const $ = id => document.getElementById(id);

/* ── Storage (this device only) ────────────────────────────── */
const Store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; } }
};

/* A stroke is {c, s, p}: c = pen colour 0-3 (or -1 for the duster), s = size 0-2,
   p = [[x, y], ...] in board pixels. Colours are stored by number, not hex, so that
   switching chalkboard ⇄ whiteboard re-inks everything in that theme's colours. */
const SIZES = {pen: [3, 6, 12], duster: [20, 40, 80]};
/* Very large screens (4K smart boards) get thicker ink and a bigger toolbar (see CSS). */
const BIG = matchMedia('(min-width: 2200px)').matches ? 1.6 : 1;
/* A touch wider than this (CSS px, ~3 cm) is a palm or the side of a hand, not a finger. */
const PALM = 100;
/* Straight lines snap level or upright when within ~6 degrees: tidy axes. */
const snap = (a, b) => { const dx = b[0] - a[0], dy = b[1] - a[1];
  return Math.abs(dy) < Math.abs(dx) * 0.1 ? [b[0], a[1]] : Math.abs(dx) < Math.abs(dy) * 0.1 ? [a[0], b[1]] : b; };
const isPt = q => Array.isArray(q) && q.length === 2 && Number.isFinite(q[0]) && Number.isFinite(q[1]);
const cleanStroke = s => s && Number.isInteger(s.c) && s.c >= -1 && s.c <= 3 && Number.isInteger(s.s) && s.s >= 0 && s.s <= 2 &&
  Array.isArray(s.p) && s.p.length && s.p.every(isPt) ? {c: s.c, s: s.s, p: s.p} : null;

function loadBoard() {
  const d = Store.get('board.pages');
  const pages = (Array.isArray(d?.pages) ? d.pages : []).map(pg => (Array.isArray(pg) ? pg : []).map(cleanStroke).filter(Boolean));
  if (!pages.length) pages.push([]);
  return {pages, i: Number.isInteger(d?.i) && d.i >= 0 && d.i < pages.length ? d.i : 0};
}
function loadPrefs() {
  const p = Store.get('board.prefs') || {};
  return {theme: p.theme === 'light' ? 'light' : 'dark', bg: ['grid', 'lines'].includes(p.bg) ? p.bg : 'plain',
    welcomed: p.welcomed === 2};          // 2 = has seen the drawing-board welcome
}
let BOARD = loadBoard(), PREFS = loadPrefs();
const savePrefs = () => Store.set('board.prefs', PREFS);

/* ── Ink: drawing, duster, undo/redo ───────────────────────── */
/* Undo history lives per page (keyed by the page itself), so it survives adding or deleting
   other pages. Clear is an undoable action too. Several fingers or pens can draw at once
   (a teacher and a student at a smart board); each pointer has its own live stroke. */
const HISTORY = new WeakMap();
const Ink = {mode: 'pen', ci: 0, si: 1, live: new Map(), penSeen: false, cols: [], cv: null, g: null,
  get strokes() { return BOARD.pages[BOARD.i]; },
  init() {
    this.cv = $('ink'); this.g = this.cv.getContext('2d');
    new ResizeObserver(() => {
      const d = devicePixelRatio || 1, r = this.cv.getBoundingClientRect();
      this.cv.width = Math.round(r.width * d); this.cv.height = Math.round(r.height * d);
      this.redraw();
    }).observe(this.cv);
    const pos = e => { const r = this.cv.getBoundingClientRect(); return [Math.round(e.clientX - r.left), Math.round(e.clientY - r.top)]; };
    /* A palm reaches the board as a wide contact (where the screen reports contact size). */
    const palm = e => e.pointerType === 'touch' && Math.max(e.width || 0, e.height || 0) > PALM;
    /* The first finger down means no other finger is down: any stroke still open for that kind
       of pointer is a ghost whose "lift" the screen never sent (smart boards drop these). */
    document.addEventListener('pointerdown', e => { if (e.isPrimary) this.finish(e.pointerType); }, true);
    this.cv.addEventListener('pointerdown', e => {
      if (e.pointerType === 'pen') this.penSeen = true;
      if (this.mode === 'off' || e.button > 0 || (e.pointerType === 'touch' && this.penSeen) || palm(e)) return;   // pen off; palm rejection
      this.finish(null, e.pointerId);                               // a reused id: close its old stroke first
      const s = {c: this.mode === 'duster' ? -1 : this.ci, s: this.si, p: [pos(e)]};
      this.live.set(e.pointerId, {s, line: this.mode === 'line', type: e.pointerType});
      this.strokes.push(s);
      this.paint(this.g, [s]);
      try { this.cv.setPointerCapture(e.pointerId); } catch {}
    });
    this.cv.addEventListener('pointermove', e => {
      const l = this.live.get(e.pointerId); if (!l) return;
      if (palm(e)) {                                                // a finger that spread into a palm: take its ink back
        this.live.delete(e.pointerId); this.strokes.splice(this.strokes.lastIndexOf(l.s), 1); return this.redraw();
      }
      if (l.line || e.shiftKey) {                                   // straight line: start point to here
        l.s.p = [l.s.p[0], snap(l.s.p[0], pos(e))]; this.redraw();
      } else {
        for (const ev of e.getCoalescedEvents?.() || [e]) l.s.p.push(pos(ev));   // every stylus sample, for smooth ink
        this.paint(this.g, [l.s]);
      }
    });
    const end = e => this.finish(null, e.pointerId);
    for (const t of ['pointerup', 'pointercancel', 'lostpointercapture']) this.cv.addEventListener(t, end);
    /* iPhone/iPad: claim every touch on the board, so long rubs with the duster never turn into
       text selection, the magnifier or a page gesture that steals the following touches. */
    for (const t of ['touchstart', 'touchmove']) this.cv.addEventListener(t, e => e.preventDefault(), {passive: false});
  },
  /* Draw strokes onto any 2D context. Points are joined with curves through their midpoints. */
  paint(g, strokes) {
    g.lineCap = g.lineJoin = 'round';
    for (const s of strokes) {
      const p = s.p, last = p[p.length - 1];
      g.globalCompositeOperation = s.c < 0 ? 'destination-out' : 'source-over';
      g.strokeStyle = s.c < 0 ? '#000' : this.cols[s.c];
      g.lineWidth = SIZES[s.c < 0 ? 'duster' : 'pen'][s.s] * BIG;
      g.beginPath(); g.moveTo(p[0][0], p[0][1]);
      for (let j = 1; j < p.length - 1; j++) g.quadraticCurveTo(p[j][0], p[j][1], (p[j][0] + p[j + 1][0]) / 2, (p[j][1] + p[j + 1][1]) / 2);
      g.lineTo(last[0] + (p.length === 1 ? 0.01 : 0), last[1]);   // a single tap still leaves a dot
      g.stroke();
    }
    g.globalCompositeOperation = 'source-over';
  },
  redraw() {
    const d = devicePixelRatio || 1;
    this.g.setTransform(d, 0, 0, d, 0, 0);
    this.g.clearRect(0, 0, this.cv.width, this.cv.height);
    this.paint(this.g, this.strokes);
  },
  /* Close open strokes: one pointer's (id), one kind's (type), or all of them (no arguments).
     The ink is already on screen, so no redraw; saving waits for a pause, so a flurry of
     contacts (a palm, several people) costs almost nothing. */
  finish(type, id) {
    for (const [k, l] of this.live) {
      if (id !== undefined ? k !== id : type && l.type !== type) continue;
      this.live.delete(k); this.record({add: l.s}); Board.saveSoon();
    }
  },
  changed() { this.redraw(); Board.save(); },
  _h() { if (!HISTORY.has(this.strokes)) HISTORY.set(this.strokes, {back: [], fwd: []}); return HISTORY.get(this.strokes); },
  record(a) { const h = this._h(); h.back.push(a); h.fwd = []; },
  undo() {
    const h = this._h(), a = h.back.pop(); if (!a) return;
    h.fwd.push(a); a.add ? this.strokes.splice(this.strokes.lastIndexOf(a.add), 1) : this.strokes.push(...a.clear); this.changed();
  },
  redo() {
    const h = this._h(), a = h.fwd.pop(); if (!a) return;
    h.back.push(a); a.add ? this.strokes.push(a.add) : this.strokes.splice(0); this.changed();
  },
  clear() { if (this.strokes.length) { this.record({clear: this.strokes.splice(0)}); this.changed(); } },
  /* tools */
  sync() {
    document.querySelectorAll('.sw').forEach((b, i) => b.classList.toggle('sel', this.mode !== 'duster' && i === this.ci));
    $('line').classList.toggle('on', this.mode === 'line');
    document.querySelectorAll('.sz').forEach((b, i) => b.classList.toggle('on', i === this.si));
    $('pen').classList.toggle('on', this.mode === 'pen');
    $('pen').setAttribute('aria-pressed', this.mode === 'pen');
    this.cv.classList.toggle('off', this.mode === 'off');
    $('duster').classList.toggle('on', this.mode === 'duster');
    this.cv.classList.toggle('duster', this.mode === 'duster');
  },
  pick(i) { this.ci = +i; if (this.mode !== 'line') this.mode = 'pen'; this.sync(); },
  size(i) { this.si = Math.max(0, Math.min(2, +i)); this.sync(); },
  pen() { this.mode = this.mode === 'pen' ? 'off' : 'pen'; this.sync(); },   // off: touch and point without marking
  line() { this.mode = this.mode === 'line' ? 'pen' : 'line'; this.sync(); },
  duster() { this.mode = this.mode === 'duster' ? 'pen' : 'duster'; this.sync(); }
};

/* ── Pages ─────────────────────────────────────────────────── */
const Board = {
  save() { clearTimeout(this.t); this.t = null; $('full').classList.toggle('hidden', Store.set('board.pages', BOARD)); },
  saveSoon() { clearTimeout(this.t); this.t = setTimeout(() => this.save(), 300); },
  show() { $('page-no').textContent = `${BOARD.i + 1} / ${BOARD.pages.length}`; Ink.redraw(); },
  /* Changing page closes any stroke still open: one stuck contact must never lock the board. */
  go(i) {
    if (!(i >= 0 && i < BOARD.pages.length)) return;
    Ink.finish(); BOARD.i = i; this.save(); this.show();
  },
  prev() { this.go(BOARD.i - 1); },
  /* Moving on from the last page gives a fresh one, but never piles up empty pages. */
  next() { BOARD.i === BOARD.pages.length - 1 && Ink.strokes.length ? this.add() : this.go(BOARD.i + 1); },
  add() { Ink.finish(); BOARD.pages.splice(BOARD.i + 1, 0, []); this.go(BOARD.i + 1); },
  /* Start fresh. If the old board has any drawing, it is saved as a picture first. */
  async fresh() {
    Ink.finish();
    const inked = BOARD.pages.some(p => p.length);
    if (inked && (!confirm('Start a new board? This one is saved as a picture first.') || !await this.download())) return;
    BOARD = {pages: [[]], i: 0}; this.save(); this.show();
  },
  remove() {
    Ink.finish();
    if (BOARD.pages.length === 1) return Ink.clear();                       // undoable
    if (Ink.strokes.length && !confirm('Delete this page and its drawing?')) return;
    BOARD.pages.splice(BOARD.i, 1);
    BOARD.i = Math.min(BOARD.i, BOARD.pages.length - 1); this.save(); this.show();
  },
  /* All pages, top to bottom, as one PNG — on the board's colour, with its grid or lines. */
  image() {
    const r = Ink.cv.getBoundingClientRect(), W = Math.round(r.width), H = Math.round(r.height);
    const k = Math.min(2, devicePixelRatio || 1), gap = 12, n = BOARD.pages.length, css = getComputedStyle(document.documentElement);
    const out = document.createElement('canvas'), layer = document.createElement('canvas');
    out.width = W * k; out.height = (n * H + (n - 1) * gap) * k; layer.width = W * k; layer.height = H * k;
    const o = out.getContext('2d'), l = layer.getContext('2d');
    o.scale(k, k); l.scale(k, k);
    o.fillStyle = css.getPropertyValue('--border'); o.fillRect(0, 0, W, out.height / k);
    BOARD.pages.forEach((pg, j) => {
      const y = j * (H + gap);
      o.fillStyle = css.getPropertyValue('--slate'); o.fillRect(0, y, W, H);
      o.fillStyle = css.getPropertyValue('--rule');
      if (PREFS.bg !== 'plain') for (let t = 40; t < H; t += 40) o.fillRect(0, y + t, W, 1);
      if (PREFS.bg === 'grid') for (let t = 40; t < W; t += 40) o.fillRect(t, y, 1, H);
      l.clearRect(0, 0, W, H); Ink.paint(l, pg);          // ink on its own layer, so the duster can't punch holes in the board
      o.drawImage(layer, 0, y, W, H);
    });
    return new Promise(res => out.toBlob(res, 'image/png'));
  },
  async download() {
    const blob = await this.image(), d = new Date();
    const name = `board-${d.toISOString().slice(0, 10)}-${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}.png`;
    const file = new File([blob], name, {type: 'image/png'});
    if (matchMedia('(pointer: coarse)').matches && navigator.canShare?.({files: [file]})) {
      try { await navigator.share({files: [file]}); return true; } catch (e) { if (e.name === 'AbortError') return false; }
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    return true;
  },
  fullscreen() {
    (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.())?.catch(() => {});
  }
};

/* ── Look: theme and background ────────────────────────────── */
const Theme = {
  apply() {
    const dark = PREFS.theme === 'dark', css = getComputedStyle(document.documentElement);
    document.documentElement.dataset.theme = PREFS.theme;
    document.querySelector('meta[name="theme-color"]').content = dark ? '#1F2B26' : '#F5F3EE';
    $('theme-btn').textContent = dark ? '☀️ Whiteboard' : '🌙 Chalkboard';
    Ink.cols = [0, 1, 2, 3].map(i => css.getPropertyValue('--c' + i).trim());
    Ink.redraw();
  },
  toggle() { PREFS.theme = PREFS.theme === 'dark' ? 'light' : 'dark'; savePrefs(); this.apply(); }
};
const Bg = {
  apply() { $('board').className = PREFS.bg === 'plain' ? '' : PREFS.bg; $('bg').textContent = 'Background: ' + PREFS.bg[0].toUpperCase() + PREFS.bg.slice(1); },
  cycle() { PREFS.bg = {plain: 'grid', grid: 'lines', lines: 'plain'}[PREFS.bg]; savePrefs(); this.apply(); }
};

/* ── Clock ─────────────────────────────────────────────────── */
const Wake = {l: null,
  async on() { try { this.l = await navigator.wakeLock?.request('screen'); } catch {} },
  off() { this.l?.release(); this.l = null; }
};
const Clock = {t0: 0, acc: 0, h: null,
  toggle() {
    if (this.h) { this.acc += Date.now() - this.t0; clearInterval(this.h); this.h = null; Wake.off(); }
    else { this.t0 = Date.now(); this.h = setInterval(() => this.show(), 500); Wake.on(); }
    this.show();
  },
  reset() { this.acc = 0; this.t0 = Date.now(); this.show(); },
  secs() { return Math.floor((this.acc + (this.h ? Date.now() - this.t0 : 0)) / 1000); },
  show() {
    const s = this.secs();
    $('clock').textContent = (this.h ? '⏸ ' : '▶ ') + String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
  }
};
document.addEventListener('visibilitychange', () => { if (!document.hidden && Clock.h) Wake.on(); });
const flush = () => { if (Board.t) Board.save(); };                     // a save still waiting is never lost
addEventListener('pagehide', flush); document.addEventListener('visibilitychange', flush);

/* ── Install ───────────────────────────────────────────────── */
/* Chrome/Edge/Brave/Android hand us an install prompt; iPhone/iPad never do, so there the
   button shows the steps instead. Hidden once Board runs as an installed app. */
const App = {prompt: null,
  installed: matchMedia('(display-mode: standalone), (display-mode: fullscreen)').matches || navigator.standalone === true,
  ios: /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1),
  show(on) { $('install').classList.toggle('hidden', !on || this.installed); },
  install() {
    if (!this.prompt) return alert('To install: tap the Share button, then "Add to Home Screen".');
    this.prompt.prompt();          // a prompt works once; the browser offers a fresh one later if declined
    this.prompt = null; this.show(false);
  }
};
addEventListener('beforeinstallprompt', e => { e.preventDefault(); App.prompt = e; App.show(true); });
addEventListener('appinstalled', () => { App.installed = true; App.show(false); });

/* ── Welcome / help card ───────────────────────────────────── */
const Help = {
  open() { $('help').showModal(); },
  close() { $('help').close(); }
};
$('help').addEventListener('close', () => { PREFS.welcomed = 2; savePrefs(); });

/* ── More menu: settings that don't need to sit on the toolbar ── */
const Menu = {
  toggle() {
    const open = $('more').classList.toggle('hidden') === false;
    $('more').style.bottom = $('bar').offsetHeight + 8 + 'px';          // just above the toolbar, however tall it is
    $('more-btn').setAttribute('aria-expanded', open);
  },
  close() { $('more').classList.add('hidden'); $('more-btn').setAttribute('aria-expanded', false); }
};

/* ── Buttons and keys ──────────────────────────────────────── */
/* Buttons carry data-do="Object.method" (and optional data-arg); no inline handlers,
   so the page can forbid inline script entirely. */
const ACTIONS = {Board, Ink, Theme, Bg, Clock, App, Help, Menu};
const run = (act, arg) => { const [o, m] = act.split('.'); ACTIONS[o]?.[m]?.(arg); };
document.addEventListener('click', e => {
  if (!e.target.closest('#more, #more-btn')) Menu.close();                // a click anywhere else closes the menu
  const el = e.target.closest('[data-do]'); if (el) run(el.dataset.do, el.dataset.arg);
});

/* Presentation clickers send Page Up / Page Down or the arrow keys. */
const KEYS = {arrowright: 'Board.next', pagedown: 'Board.next', arrowdown: 'Board.next',
  arrowleft: 'Board.prev', pageup: 'Board.prev', arrowup: 'Board.prev', n: 'Board.add',
  d: 'Ink.pen', l: 'Ink.line', x: 'Ink.duster', e: 'Ink.duster', c: 'Ink.clear', g: 'Bg.cycle', t: 'Clock.toggle',
  w: 'Theme.toggle', s: 'Board.download', f: 'Board.fullscreen', '?': 'Help.open'};
document.addEventListener('keydown', e => {
  if ($('help').open) return;                    // the dialog handles its own keys (Esc closes)
  if (e.key === 'Escape') return Menu.close();
  const k = e.key.toLowerCase(), mod = e.ctrlKey || e.metaKey;
  if (mod && k === 'z') { e.preventDefault(); return e.shiftKey ? Ink.redo() : Ink.undo(); }
  if (mod && k === 'y') { e.preventDefault(); return Ink.redo(); }
  if (mod && k === 's') { e.preventDefault(); return Board.download(); }
  if (mod || e.altKey) return;
  if (/^[1-4]$/.test(k)) return Ink.pick(k - 1);
  if (k === '[' || k === ']') return Ink.size(Ink.si + (k === ']' ? 1 : -1));
  if (KEYS[k]) { e.preventDefault(); run(KEYS[k]); }
});

/* ── Start ─────────────────────────────────────────────────── */
Ink.init();
Theme.apply();
Bg.apply();
Ink.sync();
Board.show();
Clock.show();
App.show(App.ios);
if (!PREFS.welcomed) Help.open();
if ('serviceWorker' in navigator && location.protocol !== 'file:') navigator.serviceWorker.register('sw.js');
/* Ask the browser never to clear Board's storage when the device runs low on space. */
navigator.storage?.persist?.()?.catch(() => {});
