# Board test suite: functional, offline and security checks.
# Usage:  python tests/run_full_test_suite.py [url]
# Default url is http://localhost:8080 (run `python -m http.server 8080` in the repo first).
# Set CHROME_BIN to point at a specific Chrome/Chromium/Brave binary if needed.
import hashlib
import json
import os
import sys
import tempfile
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
DOWNLOADS = tempfile.mkdtemp()

options = Options()
if os.environ.get("CHROME_BIN"):
    options.binary_location = os.environ["CHROME_BIN"]
options.add_argument('--headless=new')
options.add_argument('--window-size=1280,800')
options.add_argument('--force-device-scale-factor=1')
if hasattr(os, "geteuid") and os.geteuid() == 0:   # Linux root / containers
    options.add_argument("--no-sandbox")
options.add_experimental_option("prefs", {"download.default_directory": DOWNLOADS})
options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

driver = webdriver.Chrome(options=options)
driver.set_script_timeout(10)
driver.get(URL)
time.sleep(1)

test_results = []

# ─────────────────────────────────────────────────────────────
# VERSION LOCK (no browser needed): index.html must load app.js by its fingerprint,
# so a cached page can never run with a newer or older script.
# ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "app.js"), "rb") as fh:
    FINGERPRINT = hashlib.sha256(fh.read()).hexdigest()[:10]
with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as fh:
    _html = fh.read()
if f'<script src="app.js?v={FINGERPRINT}"></script>' in _html:
    test_results.append({'name': 'V. Script version lock', 'status': 'PASS', 'error': None})
else:
    test_results.append({'name': 'V. Script version lock', 'status': 'FAIL',
                         'error': f'app.js changed: in index.html set <script src="app.js?v={FINGERPRINT}"></script>'})

def run_test(name, fn):
    try:
        driver.get_log('browser')                       # drop anything logged before this test
        fn()
        errs = [l for l in driver.get_log('browser') if l['level'] in ['SEVERE', 'ERROR']]
        if errs:
            test_results.append({'name': name, 'status': 'FAIL', 'error': f"Console errors: {errs}"})
        else:
            test_results.append({'name': name, 'status': 'PASS', 'error': None})
    except Exception as e:
        test_results.append({'name': name, 'status': 'FAIL', 'error': str(e)})

# ── helpers ──────────────────────────────────────────────────
def js(script, *args):
    return driver.execute_script(script, *args)

def canvas():
    return driver.find_element(By.ID, "ink")

def stroke(points):
    """Draw with the mouse through points given as (x, y) offsets from the canvas's top-left."""
    cv = canvas()
    w, h = cv.size['width'], cv.size['height']
    a = ActionChains(driver).move_to_element_with_offset(cv, points[0][0] - w // 2, points[0][1] - h // 2).click_and_hold()
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        a = a.move_by_offset(x1 - x0, y1 - y0)
    a.release().perform()

def alpha(x, y):
    """Opacity of the ink canvas at (x, y): 0 = nothing drawn there."""
    return js("const g = document.getElementById('ink').getContext('2d');"
              "return g.getImageData(arguments[0] * devicePixelRatio, arguments[1] * devicePixelRatio, 1, 1).data[3];", x, y)

def press(keys):
    driver.find_element(By.TAG_NAME, "body").send_keys(keys)

def page_no():
    return driver.find_element(By.ID, "page-no").text

# ─────────────────────────────────────────────────────────────
# TEST 0: Welcome card on first visit (runs first: it is modal)
# ─────────────────────────────────────────────────────────────
def test_welcome_card():
    assert js("return document.getElementById('help').open;"), "Welcome card not shown on first visit"
    driver.find_element(By.CSS_SELECTOR, "#help [data-do='Help.close']").click()
    assert not js("return document.getElementById('help').open;"), "Welcome card did not close"
    for _ in range(20):                                 # the dialog's close event fires a moment later
        if js("return JSON.parse(localStorage.getItem('board.prefs'))?.welcomed === 2;"):
            break
        time.sleep(0.05)
    assert js("return JSON.parse(localStorage.getItem('board.prefs'))?.welcomed === 2;"), "Welcome not remembered"

run_test("0. Welcome Card (first visit)", test_welcome_card)

# ─────────────────────────────────────────────────────────────
# TEST 1: Empty board renders
# ─────────────────────────────────────────────────────────────
def test_initial_render():
    assert canvas().is_displayed(), "Drawing canvas missing"
    assert page_no() == "1 / 1", f"Expected page 1 / 1, got {page_no()}"
    assert js("return Ink.strokes.length;") == 0, "A new board should be empty"
    assert js("return document.querySelector('.sw.sel')?.dataset.arg;") == "0", "Chalk should be the default colour"
    assert "on" in driver.find_element(By.ID, "pen").get_attribute("class"), "Pen button should show the pen is active"

run_test("1. Empty Board Renders", test_initial_render)

# ─────────────────────────────────────────────────────────────
# TEST 2: Drawing with the mouse leaves ink
# ─────────────────────────────────────────────────────────────
def test_draw():
    stroke([(100, 100), (200, 100), (300, 100)])
    assert js("return Ink.strokes.length;") == 1, "Stroke was not recorded"
    assert alpha(200, 100) > 0, "No ink on the canvas where the stroke went"
    assert alpha(200, 300) == 0, "Ink appeared where nothing was drawn"

run_test("2. Drawing Leaves Ink", test_draw)

# ─────────────────────────────────────────────────────────────
# TEST 3: Colour and size selection
# ─────────────────────────────────────────────────────────────
def test_colour_and_size():
    driver.find_element(By.CSS_SELECTOR, ".sw[data-arg='2']").click()
    driver.find_element(By.CSS_SELECTOR, ".sz[data-arg='2']").click()
    stroke([(100, 200), (300, 200)])
    s = js("return Ink.strokes.at(-1);")
    assert s['c'] == 2 and s['s'] == 2, f"Stroke should be colour 2, size 2, got {s['c']}, {s['s']}"
    assert alpha(200, 205) > 0, "Thick stroke should cover 5px off its centre line"
    press("1")
    assert js("return Ink.ci;") == 0, "Key 1 did not pick colour 1"
    press("[")
    assert js("return Ink.si;") == 1, "Key [ did not make the pen thinner"

run_test("3. Colour and Size", test_colour_and_size)

# ─────────────────────────────────────────────────────────────
# TEST 4: Duster rubs out ink
# ─────────────────────────────────────────────────────────────
def test_duster():
    driver.find_element(By.ID, "duster").click()
    assert js("return Ink.mode;") == 'duster', "Duster button did not switch to duster"
    assert "on" in driver.find_element(By.ID, "duster").get_attribute("class"), "Duster button not highlighted"
    stroke([(200, 60), (200, 140)])
    assert js("return Ink.strokes.at(-1).c;") == -1, "Duster stroke not marked as eraser"
    assert alpha(200, 100) == 0, "Duster did not erase the ink under it"
    assert alpha(120, 100) > 0, "Duster erased ink it never touched"
    driver.find_element(By.ID, "duster").click()
    assert js("return Ink.mode;") == 'pen', "Second click should return to the pen"
    driver.find_element(By.ID, "duster").click()
    driver.find_element(By.ID, "pen").click()
    assert js("return Ink.mode;") == 'pen', "Pen button did not switch back from the duster"
    assert "on" not in driver.find_element(By.ID, "duster").get_attribute("class"), "Duster still highlighted"

run_test("4. Duster Rubs Out", test_duster)

# ─────────────────────────────────────────────────────────────
# TEST 4b: Pen switches off, so the board can be touched without marking
# ─────────────────────────────────────────────────────────────
def test_pen_toggle():
    pen = driver.find_element(By.ID, "pen")
    n = js("return Ink.strokes.length;")
    pen.click()
    assert js("return Ink.mode;") == 'off' and "on" not in pen.get_attribute("class"), "Pen button did not switch the pen off"
    assert pen.get_attribute("aria-pressed") == "false", "Pen button should report it is off to screen readers"
    stroke([(500, 500), (600, 520), (700, 500)])
    assert js("return Ink.strokes.length;") == n and alpha(600, 515) == 0, "Pen off still left a mark"
    press("d")
    assert js("return Ink.mode;") == 'pen', "D did not turn the pen back on"
    press("d")
    driver.find_element(By.CSS_SELECTOR, ".sw[data-arg='0']").click()
    assert js("return Ink.mode;") == 'pen', "Picking a colour should switch the pen back on"
    stroke([(500, 500), (600, 520)])
    assert js("return Ink.strokes.length;") == n + 1, "Pen back on does not draw"
    js("Ink.undo();")

run_test("4b. Pen On / Off", test_pen_toggle)

# ─────────────────────────────────────────────────────────────
# TEST 5: Undo / redo, and undoing a Clear
# ─────────────────────────────────────────────────────────────
def test_undo_redo_clear():
    n = js("return Ink.strokes.length;")
    js("Ink.undo();")
    assert js("return Ink.strokes.length;") == n - 1, "Undo did not remove the last stroke"
    js("Ink.redo();")
    assert js("return Ink.strokes.length;") == n, "Redo did not bring the stroke back"
    press("c")
    assert js("return Ink.strokes.length;") == 0, "Clear did not empty the page"
    assert alpha(120, 100) == 0, "Canvas not cleared"
    js("Ink.undo();")
    assert js("return Ink.strokes.length;") == n, "Undo did not restore a cleared page"
    assert alpha(120, 100) > 0, "Restored ink not drawn"

run_test("5. Undo, Redo and Undo-Clear", test_undo_redo_clear)

# ─────────────────────────────────────────────────────────────
# TEST 6: Pages
# ─────────────────────────────────────────────────────────────
def test_pages():
    inked = js("return Ink.strokes.length;")
    press("n")
    assert page_no() == "2 / 2", f"New page: expected 2 / 2, got {page_no()}"
    assert js("return Ink.strokes.length;") == 0 and alpha(120, 100) == 0, "New page is not blank"
    js("Board.next();")
    assert page_no() == "2 / 2", "Next on an empty last page should not add another empty page"
    stroke([(400, 400), (500, 400)])
    js("Board.next();")
    assert page_no() == "3 / 3", "Next on an inked last page should add a fresh page"
    press("")                                    # left arrow
    press("")                                    # Page Up (clickers)
    assert page_no() == "1 / 3", f"Arrow / Page Up did not flip back, got {page_no()}"
    assert js("return Ink.strokes.length;") == inked, "Page 1 lost its ink"
    js("Board.go(2); window.confirm = () => true; Board.remove();")
    assert page_no() == "2 / 2", f"Delete page failed, got {page_no()}"

run_test("6. Pages: Add, Flip, Delete", test_pages)

# ─────────────────────────────────────────────────────────────
# TEST 7: The board survives a reload
# ─────────────────────────────────────────────────────────────
def test_persistence():
    before = js("return BOARD.pages.map(p => p.length);")
    driver.refresh(); time.sleep(0.8)
    after = js("return BOARD.pages.map(p => p.length);")
    assert after == before, f"Pages changed across reload: {before} -> {after}"
    assert not js("return document.getElementById('help').open;"), "Welcome card came back after closing it"

run_test("7. Board Survives Reload", test_persistence)

# ─────────────────────────────────────────────────────────────
# TEST 8: Theme re-inks colours; background modes
# ─────────────────────────────────────────────────────────────
def test_theme_and_background():
    dark = js("return Ink.cols[0];")
    press("w")
    assert js("return PREFS.theme;") == 'light', "Theme did not switch"
    assert js("return Ink.cols[0];") != dark, "Chalk colour did not change with the theme (white on white)"
    press("w")
    for expect in ["grid", "lines", ""]:
        press("g")
        assert driver.find_element(By.ID, "board").get_attribute("class") == expect, f"Background should be '{expect or 'plain'}'"

run_test("8. Theme and Background", test_theme_and_background)

# ─────────────────────────────────────────────────────────────
# TEST 9: Clock
# ─────────────────────────────────────────────────────────────
def test_clock():
    press("t")
    time.sleep(1.6)
    assert js("return Clock.secs();") >= 1, "Clock did not run"
    assert "00:00" not in driver.find_element(By.ID, "clock").text, "Clock display did not update"
    press("t")
    paused = js("return Clock.secs();")
    time.sleep(1.1)
    assert js("return Clock.secs();") == paused, "Clock kept running while paused"
    js("Clock.reset();")
    assert js("return Clock.secs();") == 0, "Clock did not reset"

run_test("9. Clock", test_clock)

# ─────────────────────────────────────────────────────────────
# TEST 10: Save produces one picture of every page
# ─────────────────────────────────────────────────────────────
def test_save_image():
    size = driver.execute_async_script("""
      const done = arguments[arguments.length - 1];
      Board.image().then(b => createImageBitmap(b)).then(i => done([i.width, i.height, BOARD.pages.length]));""")
    w, h, n = size
    cv = canvas().size
    assert w == cv['width'], f"Image width {w} != board width {cv['width']}"
    assert h == n * cv['height'] + (n - 1) * 12, f"Image height {h} does not fit {n} pages"
    press("s")
    for _ in range(20):
        files = [f for f in os.listdir(DOWNLOADS) if f.endswith(".png")]
        if files:
            break
        time.sleep(0.25)
    assert files and files[0].startswith("board-"), f"Save did not download a PNG: {os.listdir(DOWNLOADS)}"

run_test("10. Save All Pages as One Picture", test_save_image)

# ─────────────────────────────────────────────────────────────
# TEST 11: Keyboard: pen / duster keys and Ctrl+Z
# ─────────────────────────────────────────────────────────────
def test_keyboard():
    press("x")
    assert js("return Ink.mode;") == 'duster', "X did not pick the duster"
    press("d")
    assert js("return Ink.mode;") == 'pen', "D did not pick the pen"
    stroke([(600, 300), (700, 320)])                   # undo history starts fresh after a reload
    n = js("return Ink.strokes.length;")
    ActionChains(driver).key_down("").send_keys("z").key_up("").perform()        # Ctrl+Z
    assert js("return Ink.strokes.length;") == n - 1, "Ctrl+Z did not undo"
    ActionChains(driver).key_down("").key_down("").send_keys("z").key_up("").key_up("").perform()
    assert js("return Ink.strokes.length;") == n, "Ctrl+Shift+Z did not redo"

run_test("11. Keyboard Shortcuts", test_keyboard)

# ─────────────────────────────────────────────────────────────
# TEST 12: Stylus palm rejection
# ─────────────────────────────────────────────────────────────
def test_palm_rejection():
    n = js("return Ink.strokes.length;")
    js("""
      const cv = document.getElementById('ink'), r = cv.getBoundingClientRect();
      const ev = (t, type, id, x) => cv.dispatchEvent(new PointerEvent(t, {pointerType: type, pointerId: id, bubbles: true,
        clientX: r.left + x, clientY: r.top + 500, isPrimary: true}));
      ev('pointerdown', 'pen', 7, 100); ev('pointermove', 'pen', 7, 160); ev('pointerup', 'pen', 7, 160);
      ev('pointerdown', 'touch', 8, 300); ev('pointermove', 'touch', 8, 360); ev('pointerup', 'touch', 8, 360);""")
    assert js("return Ink.strokes.length;") == n + 1, "Stylus should draw and a resting palm (touch) should not"
    js("Ink.penSeen = false;")

run_test("12. Stylus Palm Rejection", test_palm_rejection)

# ─────────────────────────────────────────────────────────────
# TEST 12b: Line tool, Shift+drag, and snapping
# ─────────────────────────────────────────────────────────────
def test_line_tool():
    js("Board.add();")                                  # a clean page for pixel checks
    driver.find_element(By.ID, "line").click()
    assert js("return Ink.mode;") == 'line', "Line button did not select the line tool"
    stroke([(100, 300), (180, 360), (300, 304)])        # a wiggly path ending ~level with the start
    s = js("return Ink.strokes.at(-1);")
    assert len(s['p']) == 2, f"A line should keep only its two ends, has {len(s['p'])} points"
    assert s['p'][1][1] == s['p'][0][1], f"Nearly-level line should snap level: {s['p']}"
    assert alpha(200, 300) > 0, "No ink along the straight line"
    assert alpha(180, 360) == 0, "The wiggle was drawn: the line is not straight"
    press("l")
    assert js("return Ink.mode;") == 'pen', "L should switch the line tool off again"
    ActionChains(driver).key_down("\ue008").perform()   # hold Shift with the pen
    stroke([(100, 500), (200, 560), (300, 600)])
    ActionChains(driver).key_up("\ue008").perform()
    s = js("return Ink.strokes.at(-1);")
    assert len(s['p']) == 2, "Shift+drag should draw a straight line"

run_test("12b. Line Tool and Shift+Drag", test_line_tool)

# ─────────────────────────────────────────────────────────────
# TEST 12c: Two people drawing at once; undo removes the right stroke
# ─────────────────────────────────────────────────────────────
def test_multi_touch():
    n = js("return Ink.strokes.length;")
    js("""
      const cv = document.getElementById('ink'), r = cv.getBoundingClientRect();
      const ev = (t, id, x, y) => cv.dispatchEvent(new PointerEvent(t, {pointerType: 'touch', pointerId: id, bubbles: true,
        clientX: r.left + x, clientY: r.top + y}));
      ev('pointerdown', 21, 100, 150); ev('pointerdown', 22, 600, 150);      // A and B start together
      ev('pointermove', 21, 160, 160); ev('pointermove', 22, 660, 160);
      ev('pointerup', 22, 660, 160); ev('pointerup', 21, 160, 160);          // B lifts first""")
    assert js("return Ink.strokes.length;") == n + 2, "Two simultaneous fingers should draw two strokes"
    js("Ink.undo();")                                   # A finished last, so undo removes A
    left = js("return Ink.strokes.slice(-1)[0].p[0][0];")
    assert js("return Ink.strokes.length;") == n + 1 and left == 600, f"Undo removed the wrong stroke (left starts at x={left})"
    js("Ink.undo();")

run_test("12c. Several People Drawing at Once", test_multi_touch)

# ─────────────────────────────────────────────────────────────
# TEST 12d: More menu and New board
# ─────────────────────────────────────────────────────────────
def test_menu_and_new_board():
    menu = driver.find_element(By.ID, "more")
    driver.find_element(By.ID, "more-btn").click()
    assert menu.is_displayed(), "More menu did not open"
    ActionChains(driver).move_to_element_with_offset(canvas(), 0, 0).click().perform()
    assert not menu.is_displayed(), "Clicking the board should close the menu"
    driver.find_element(By.ID, "more-btn").click()
    press("\ue00c")                                     # Escape
    assert not menu.is_displayed(), "Escape should close the menu"
    pages = js("return BOARD.pages.length;")
    js("window.confirm = () => false; Board.fresh();")
    assert js("return BOARD.pages.length;") == pages, "Cancelling New board must keep the board"
    before = len(os.listdir(DOWNLOADS))
    driver.execute_async_script("const done = arguments[arguments.length - 1]; window.confirm = () => true; Board.fresh().then(done);")
    assert js("return [BOARD.pages.length, Ink.strokes.length];") == [1, 0], "New board did not start fresh"
    assert page_no() == "1 / 1", f"Page counter not reset: {page_no()}"
    for _ in range(20):
        if len(os.listdir(DOWNLOADS)) > before:
            break
        time.sleep(0.25)
    assert len(os.listdir(DOWNLOADS)) > before, "The old board was not saved as a picture first"

run_test("12d. More Menu and New Board", test_menu_and_new_board)

# ─────────────────────────────────────────────────────────────
# TEST 12e: Touch-screen hardening (iPhone/iPad gestures can't steal strokes)
# ─────────────────────────────────────────────────────────────
def test_touch_hardening():
    css = js("""const b = getComputedStyle(document.body), c = getComputedStyle(document.getElementById('ink'));
                return [b.userSelect || b.webkitUserSelect, c.touchAction,
                        getComputedStyle(document.querySelector('#bar button')).touchAction];""")
    assert css[0] == 'none', f"Text selection must be off on the board (iOS magnifier), got {css[0]}"
    assert css[1] == 'none', f"Board must claim all touch gestures, got touch-action {css[1]}"
    assert css[2] == 'manipulation', f"Toolbar buttons should not double-tap zoom, got {css[2]}"
    blocked = js("""const e = new TouchEvent('touchstart', {cancelable: true, bubbles: true});
                    document.getElementById('ink').dispatchEvent(e); return e.defaultPrevented;""")
    assert blocked, "Touches on the board are not claimed (iOS could start a selection or scroll)"
    n = js("return Ink.strokes.length;")
    js("""const cv = document.getElementById('ink'), r = cv.getBoundingClientRect();
          const ev = (t, x) => cv.dispatchEvent(new PointerEvent(t, {pointerType: 'touch', pointerId: 31, bubbles: true,
            clientX: r.left + x, clientY: r.top + 200}));
          ev('pointerdown', 100); ev('pointermove', 150); ev('lostpointercapture', 150);""")
    assert js("return Ink.live.size;") == 0, "A touch taken over by the system left a stroke stuck open"
    assert js("return Ink.strokes.length;") == n + 1, "The interrupted stroke was not kept"
    js("Ink.undo();")

run_test("12e. Touch-Screen Hardening", test_touch_hardening)

# ─────────────────────────────────────────────────────────────
# TEST 13: Offline service worker
# ─────────────────────────────────────────────────────────────
def test_service_worker():
    ok = driver.execute_async_script("""
      const done = arguments[arguments.length - 1];
      if (!('serviceWorker' in navigator)) return done('no-sw-support');
      navigator.serviceWorker.ready.then(r => done(!!r.active)).catch(e => done(String(e)));""")
    assert ok is True, f"Service worker not active: {ok}"
    cached = driver.execute_async_script("""
      const done = arguments[arguments.length - 1];
      caches.keys().then(k => Promise.all(k.map(n => caches.open(n).then(c => c.keys()))))
        .then(all => done(all.flat().map(r => new URL(r.url).pathname)));""")
    for f in ["/index.html", "/app.js", "/manifest.webmanifest", "/icons/icon-192.png"]:
        assert any(c.endswith(f) for c in cached), f"{f} not cached for offline use"
    script = js("return new URL(document.querySelector('script[src]').src).search;")
    exact = driver.execute_async_script("""
      const done = arguments[arguments.length - 1];
      caches.match(document.querySelector('script[src]').src).then(r => done(!!r));""")
    assert script.startswith("?v=") and exact, f"The exact script version this page needs ({script}) is not cached"

run_test("13. Offline Service Worker", test_service_worker)

# ─────────────────────────────────────────────────────────────
# SECURITY TESTS — each one is a real attack; all must stay harmless
# ─────────────────────────────────────────────────────────────
def pwned():
    return js("return Object.keys(window).filter(k => k.startsWith('__pwn'));")

def test_tampered_storage():
    js("""localStorage.setItem('board.pages', JSON.stringify({i: '<img src=x onerror=window.__pwn1=1>', pages: [
          [{c: 0, s: 1, p: [[10, 10], [20, 20]]}],
          [{c: '<img src=x onerror=window.__pwn2=1>', s: 1, p: [[1, 1]]}, {c: 9, s: 1, p: [[1, 1]]},
           {c: 1, s: 99, p: [[1, 1]]}, {c: 1, s: 1, p: [['x', 'y']]}, {c: 1, s: 1, p: 'nope'}, null, 'text'],
          'not a page']}));
        localStorage.setItem('board.prefs', JSON.stringify({theme: '"><img src=x onerror=window.__pwn3=1>',
          bg: 'grid <script>window.__pwn4=1</script>', welcomed: 2}));""")
    driver.refresh(); time.sleep(0.8)
    assert not pwned(), f"Stored data ran code: {pwned()}"
    pages = js("return BOARD.pages.map(p => p.length);")
    assert pages == [1, 0, 0], f"Bad strokes should be dropped, valid ones kept: {pages}"
    assert js("return [PREFS.theme, PREFS.bg, BOARD.i];") == ['dark', 'plain', 0], "Bad prefs were not reset to safe defaults"
    assert page_no() == "1 / 3", f"Board did not recover: {page_no()}"
    stroke([(100, 100), (150, 120)])
    assert js("return Ink.strokes.length;") == 2, "Board unusable after loading tampered data"

run_test("14. Security: tampered saved data", test_tampered_storage)

def test_csp_blocks_inline_script():
    csp = js("return document.querySelector('meta[http-equiv=Content-Security-Policy]')?.content || '';")
    script_src = next((d for d in csp.split(";") if d.strip().startswith("script-src")), "")
    assert script_src and "unsafe" not in script_src, f"script-src missing or weakened: {csp!r}"
    # Simulate a future bug that lets markup through: the browser must still refuse to run it
    js("document.getElementById('board').insertAdjacentHTML('beforeend',"
       "'<img src=\"data:,\" onerror=\"window.__pwn8=1\" onload=\"window.__pwn8=1\">');")
    time.sleep(0.3)
    driver.get_log('browser')               # the CSP violation report is expected here
    assert not pwned(), f"Inline handler ran despite CSP: {pwned()}"
    inline = js("return document.querySelectorAll('[onclick],[onchange],[oninput],[onload],[onerror]').length;")
    assert inline <= 1, "Inline event handlers found in the page; use data-do instead"

run_test("15. Security: CSP blocks inline script", test_csp_blocks_inline_script)

# ─────────────────────────────────────────────────────────────
# TEST 16: Install button
# ─────────────────────────────────────────────────────────────
def test_install_button():
    btn = driver.find_element(By.ID, "install")
    offered = js("return !!App.prompt;")   # Chrome may already have offered a real install
    assert btn.is_displayed() == offered, f"Install button visible={btn.is_displayed()} but browser offered install={offered}"
    js("""const e = new Event('beforeinstallprompt', {cancelable: true});
          e.prompt = () => { window.__prompted = true; };
          dispatchEvent(e);""")
    assert btn.is_displayed(), "Install button did not appear when install became available"
    btn.click()
    assert js("return window.__prompted === true;"), "Install button did not open the install prompt"
    assert not btn.is_displayed(), "Install button should hide after use"
    js("dispatchEvent(new Event('beforeinstallprompt')); dispatchEvent(new Event('appinstalled'));")
    assert not btn.is_displayed(), "Install button should hide once installed"

run_test("16. Install Button", test_install_button)

# ─────────────────────────────────────────────────────────────
# TEST 17: Help reopens with ? and the button
# ─────────────────────────────────────────────────────────────
def test_help():
    press("?")
    assert js("return document.getElementById('help').open;"), "'?' did not open help"
    n = js("return Ink.strokes.length;")
    press("c")                                          # keys must not reach the board while help is open
    assert js("return Ink.strokes.length;") == n, "A shortcut fired behind the help card"
    driver.find_element(By.CSS_SELECTOR, "#help [data-do='Help.close']").click()
    driver.find_element(By.CSS_SELECTOR, "#bar [data-do='Help.open']").click()
    assert js("return document.getElementById('help').open;"), "Help button did not open help"
    js("Help.close();")

run_test("17. Help Card", test_help)

# ─────────────────────────────────────────────────────────────
# TEST 18: Very large screens get thicker ink and a bigger toolbar
# ─────────────────────────────────────────────────────────────
def test_big_screen():
    driver.set_window_size(2600, 1200); driver.refresh(); time.sleep(0.8)
    try:
        assert js("return BIG;") > 1, "4K-wide screen should get thicker ink"
        assert js("return parseFloat(getComputedStyle(document.getElementById('bar')).zoom);") > 1, "Toolbar should be enlarged"
    finally:
        driver.set_window_size(1280, 800); driver.refresh(); time.sleep(0.8)
    assert js("return BIG;") == 1, "Normal screens should keep normal ink"

run_test("18. Large Smart-Board Screens", test_big_screen)

# Leave the browser profile clean
js("localStorage.clear();")
driver.quit()

print(json.dumps(test_results, indent=2))
passed = sum(r["status"] == "PASS" for r in test_results)
print(f"\n{passed}/{len(test_results)} passed")
sys.exit(0 if passed == len(test_results) else 1)
