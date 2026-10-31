import time
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Usage:  python tests/run_full_test_suite.py [url]
# Default url is http://localhost:8080 (run `python -m http.server 8080` in the repo first).
# Set CHROME_BIN to point at a specific Chrome/Chromium/Brave binary if needed.
import sys
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"

options = Options()
if os.environ.get("CHROME_BIN"):
    options.binary_location = os.environ["CHROME_BIN"]
if hasattr(os, "geteuid") and os.geteuid() == 0:   # Linux root / containers
    options.add_argument("--no-sandbox")
options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
options.add_argument('--headless=new')
options.add_argument('--window-size=1280,800')
options.add_argument('--force-device-scale-factor=1')

driver = webdriver.Chrome(options=options)
driver.get(URL)
time.sleep(1)

test_results = []

def run_test(name, fn):
    try:
        # Check browser console logs before test
        logs_before = driver.get_log('browser')
        fn()
        # Check console logs after test for errors
        logs_after = driver.get_log('browser')
        errs = [l for l in logs_after if l['level'] in ['SEVERE', 'ERROR']]
        if errs:
            test_results.append({'name': name, 'status': 'FAIL', 'error': f"Console errors: {errs}"})
        else:
            test_results.append({'name': name, 'status': 'PASS', 'error': None})
    except Exception as e:
        test_results.append({'name': name, 'status': 'FAIL', 'error': str(e)})

# ─────────────────────────────────────────────────────────────
# TEST 0: Welcome card on first visit (must run first: it is modal)
# ─────────────────────────────────────────────────────────────
def test_welcome_card():
    assert driver.execute_script("return document.getElementById('help').open;"), "Welcome card not shown on first visit"
    driver.find_element(By.CSS_SELECTOR, "#help [data-do='Help.close']").click()
    assert not driver.execute_script("return document.getElementById('help').open;"), "Welcome card did not close"
    assert driver.execute_script("return JSON.parse(localStorage.getItem('board.prefs')).welcomed === true;"), "Welcome not remembered"

run_test("0. Welcome Card (first visit)", test_welcome_card)

# ─────────────────────────────────────────────────────────────
# TEST 1: Initial Render & DOM Structure
# ─────────────────────────────────────────────────────────────
def test_initial_render():
    title = driver.find_element(By.ID, "title").text
    assert "Welcome to Board" in title, f"Unexpected title: {title}"
    count = driver.find_element(By.ID, "count").text
    assert "Line 0" in count, f"Unexpected count: {count}"
    assert driver.find_element(By.ID, "ink").is_displayed(), "Canvas overlay missing"

run_test("1. Initial Render & DOM Structure", test_initial_render)

# ─────────────────────────────────────────────────────────────
# TEST 2: Line-by-Line Reveal Navigation
# ─────────────────────────────────────────────────────────────
def test_line_reveal():
    # Step forward 3 times using B.next()
    driver.execute_script("B.next(); B.next(); B.next();")
    count = driver.find_element(By.ID, "count").text
    assert "Line 3" in count, f"Expected Line 3, got {count}"
    
    # Check visible steps
    visible_steps = driver.find_elements(By.CSS_SELECTOR, "#steps .step:not(.hidden)")
    assert len(visible_steps) == 3, f"Expected 3 visible steps, got {len(visible_steps)}"
    
    # Step backward 1 time using B.prev()
    driver.execute_script("B.prev();")
    count = driver.find_element(By.ID, "count").text
    assert "Line 2" in count, f"Expected Line 2, got {count}"

run_test("2. Line-by-Line Reveal Navigation", test_line_reveal)

# ─────────────────────────────────────────────────────────────
# TEST 3: Slide Navigation & Jump
# ─────────────────────────────────────────────────────────────
def test_slide_jump():
    # Jump to slide 2 (index 1)
    driver.execute_script("B.go(1);")
    title = driver.find_element(By.ID, "title").text
    assert "Write in plain text" in title, f"Expected slide 2 title 'Write in plain text', got '{title}'"
    
    # Jump back to slide 1 (index 0)
    driver.execute_script("B.go(0);")
    title = driver.find_element(By.ID, "title").text
    assert "Welcome to Board" in title, f"Expected slide 1 title 'Welcome to Board', got '{title}'"

run_test("3. Slide Navigation & Jump", test_slide_jump)

# ─────────────────────────────────────────────────────────────
# TEST 4: Ink Drawing & Color Selection
# ─────────────────────────────────────────────────────────────
def test_ink_drawing():
    # Toggle pen on
    driver.execute_script("Ink.on = true; Ink.mode = 'pen'; Ink._updateBtns();")
    pen_btn = driver.find_element(By.ID, "pen")
    assert "Pen on" in pen_btn.text, f"Expected button text 'Pen on', got {pen_btn.text}"
    
    # Draw stroke
    driver.execute_script("""
      const s = {c: Ink.col, p: [[100, 100], [150, 150], [200, 100]]};
      (Ink.strokes[B.i] ??= []).push(s);
      Ink.redraw();
    """)
    strokes = driver.execute_script("return Ink.strokes[B.i];")
    assert len(strokes) >= 1, "Stroke was not recorded in Ink.strokes"
    assert strokes[-1]['c'] == driver.execute_script("return Ink.col;"), "Stroke color mismatch"

run_test("4. Ink Drawing & Color Selection", test_ink_drawing)

# ─────────────────────────────────────────────────────────────
# TEST 5: Duster Erasing Feature
# ─────────────────────────────────────────────────────────────
def test_duster():
    # Toggle duster on
    driver.execute_script("Ink.toggleDuster();")
    duster_btn = driver.find_element(By.ID, "duster")
    assert "on" in duster_btn.get_attribute("class"), "Duster button missing 'on' active class"
    assert driver.execute_script("return Ink.mode;") == 'duster', "Ink mode is not 'duster'"
    
    # Add duster stroke
    driver.execute_script("""
      const s = {e: true, p: [[120, 120], [180, 120]]};
      (Ink.strokes[B.i] ??= []).push(s);
      Ink.redraw();
    """)
    strokes = driver.execute_script("return Ink.strokes[B.i];")
    assert strokes[-1].get('e') == True, "Duster eraser flag e:true missing on stroke"

run_test("5. Duster Erasing Feature", test_duster)

# ─────────────────────────────────────────────────────────────
# TEST 6: Undo / Redo / Clear Ink
# ─────────────────────────────────────────────────────────────
def test_undo_clear():
    initial_count = driver.execute_script("return Ink.strokes[B.i].length;")
    # Perform Undo
    driver.execute_script("Ink.undo();")
    after_undo_count = driver.execute_script("return Ink.strokes[B.i].length;")
    assert after_undo_count == initial_count - 1, f"Undo failed: {after_undo_count} vs {initial_count - 1}"
    
    # Perform Redo
    driver.execute_script("Ink.redo();")
    after_redo_count = driver.execute_script("return Ink.strokes[B.i].length;")
    assert after_redo_count == initial_count, f"Redo failed: {after_redo_count} vs {initial_count}"
    
    # Clear ink
    driver.execute_script("Ink.clear();")
    cleared_count = driver.execute_script("return Ink.strokes[B.i].length;")
    assert cleared_count == 0, f"Clear ink failed, strokes length: {cleared_count}"

run_test("6. Undo / Redo / Clear Ink", test_undo_clear)

# ─────────────────────────────────────────────────────────────
# TEST 7: Theme & Palette Synchronization
# ─────────────────────────────────────────────────────────────
def test_theme():
    initial_theme = driver.execute_script("return PREFS.theme;")
    # Toggle Theme
    driver.execute_script("Theme.toggle();")
    new_theme = driver.execute_script("return PREFS.theme;")
    assert new_theme != initial_theme, "Theme did not toggle"
    
    # Toggle back
    driver.execute_script("Theme.toggle();")
    reverted_theme = driver.execute_script("return PREFS.theme;")
    assert reverted_theme == initial_theme, "Theme did not revert"

run_test("7. Theme & Palette Synchronization", test_theme)

# ─────────────────────────────────────────────────────────────
# TEST 8: Font Size Scaling Bounds
# ─────────────────────────────────────────────────────────────
def test_font_scale():
    # Levels are 75 / 88 / 100 / 125 / 150 %; default is 100% (level 2)
    driver.execute_script("PREFS.fontLevel = 2; Font._apply();")
    driver.execute_script("Font.up();")
    level = driver.find_element(By.ID, "font-level").text
    assert level == "125%", f"Expected 125%, got {level}"

    # Upper bound: pressing up past the top stays at 150%
    driver.execute_script("Font.up(); Font.up(); Font.up();")
    level = driver.find_element(By.ID, "font-level").text
    assert level == "150%", f"Expected 150% cap, got {level}"

    # Lower bound: pressing down past the bottom stays at 75%
    driver.execute_script("for (let i = 0; i < 8; i++) Font.down();")
    level = driver.find_element(By.ID, "font-level").text
    assert level == "75%", f"Expected 75% floor, got {level}"

    # Reset font
    driver.execute_script("PREFS.fontLevel = 2; Font._apply();")

run_test("8. Font Size Scaling Bounds", test_font_scale)

# ─────────────────────────────────────────────────────────────
# TEST 9: Countdown Clock Timer
# ─────────────────────────────────────────────────────────────
def test_clock():
    # Start clock
    driver.execute_script("Clock.toggle();")
    assert driver.execute_script("return Clock.h !== null;"), "Clock timer handle is null after toggle"
    time.sleep(1.6)
    secs = driver.execute_script("return Math.floor((Clock.acc + Date.now() - Clock.t0) / 1000);")
    assert secs >= 1, f"Clock seconds did not increment: {secs}"
    shown = driver.find_element(By.ID, "clock").text
    assert shown != "00:00", f"Clock display did not update: {shown}"
    # Stop clock
    driver.execute_script("Clock.toggle();")

run_test("9. Countdown Clock Timer", test_clock)

# ─────────────────────────────────────────────────────────────
# TEST 10: Lecture Editor & Live Parser
# ─────────────────────────────────────────────────────────────
def test_editor():
    # Open Editor
    driver.execute_script("Ed.open();")
    editor = driver.find_element(By.ID, "editor")
    assert not ("hidden" in editor.get_attribute("class")), "Editor overlay not visible"
    
    # Save test lecture
    test_markdown = "# Test Title\\n> Subtitle test\\nFirst step line\\nSecond step line"
    driver.execute_script(f"document.getElementById('src').value = `{test_markdown}`; Ed.save(); Ed.close();")
    
    title = driver.find_element(By.ID, "title").text
    assert title == "Test Title", f"Editor save failed, expected 'Test Title', got '{title}'"

run_test("10. Lecture Editor & Live Parser", test_editor)

# ─────────────────────────────────────────────────────────────
# TEST 11: Lecture Library Persistence
# ─────────────────────────────────────────────────────────────
def test_library():
    # Open Library
    driver.execute_script("Lib.open();")
    lib = driver.find_element(By.ID, "library")
    assert not ("hidden" in lib.get_attribute("class")), "Library overlay not visible"
    
    # Check library list items
    items = driver.find_elements(By.CSS_SELECTOR, ".lib-item")
    assert len(items) >= 1, "No lectures found in library list"
    
    driver.execute_script("Lib.close();")

run_test("11. Lecture Library Persistence", test_library)

# ─────────────────────────────────────────────────────────────
# TEST 12: Keyboard Shortcut Event Listeners
# ─────────────────────────────────────────────────────────────
def test_keyboard_shortcuts():
    # Start from a known state: ink off, pen mode (earlier tests left the duster on)
    driver.execute_script("Ink.on = false; Ink.mode = 'pen'; Ink._updateBtns();")
    body = driver.find_element(By.TAG_NAME, "body")
    # Press 'X' for duster
    body.send_keys("x")
    assert driver.execute_script("return Ink.mode;") == 'duster', "Keyboard 'X' failed to activate duster"
    
    assert driver.execute_script("return Ink.on;") is True, "Keyboard 'X' did not switch ink on"

    # Press 'D': toggles ink off and falls back to pen mode
    body.send_keys("d")
    assert driver.execute_script("return Ink.mode;") == 'pen', "Keyboard 'D' failed to reset to pen"
    assert driver.execute_script("return Ink.on;") is False, "Keyboard 'D' did not toggle ink off"

    # Press 'D' again: pen on
    body.send_keys("d")
    assert driver.execute_script("return Ink.on && Ink.mode === 'pen';"), "Keyboard 'D' failed to activate pen"

run_test("12. Keyboard Shortcut Event Listeners", test_keyboard_shortcuts)

# ─────────────────────────────────────────────────────────────
# TEST 13: Offline service worker
# ─────────────────────────────────────────────────────────────
def test_service_worker():
    ok = driver.execute_async_script("""
      const done = arguments[arguments.length - 1];
      if (!('serviceWorker' in navigator)) return done('no-sw-support');
      navigator.serviceWorker.ready.then(r => done(!!r.active)).catch(e => done(String(e)));
    """)
    assert ok is True, f"Service worker not active: {ok}"
    cached = driver.execute_async_script("""
      const done = arguments[arguments.length - 1];
      caches.keys().then(k => Promise.all(k.map(n => caches.open(n).then(c => c.keys()))))
        .then(all => done(all.flat().map(r => new URL(r.url).pathname)));
    """)
    for f in ["/index.html", "/app.js", "/manifest.webmanifest", "/icons/icon-192.png"]:
        assert any(c.endswith(f) for c in cached), f"{f} not cached for offline use"

driver.set_script_timeout(10)
run_test("13. Offline Service Worker", test_service_worker)

# ─────────────────────────────────────────────────────────────
# SECURITY TESTS — each one is a real attack; all must stay harmless
# ─────────────────────────────────────────────────────────────
import tempfile
from selenium.webdriver.common.action_chains import ActionChains

def pwned():
    return driver.execute_script("return Object.keys(window).filter(k => k.startsWith('__pwn'));")

def test_malicious_backup():
    evil = {"lectures": [
        {"id": "a');window.__pwn1=1;('", "name": "id attack", "content": "# A", "modified": 1},
        {"id": "b1", "name": "\" onmouseover=\"window.__pwn2=1\" x=\"", "content": "# B", "modified": 2},
        {"id": "c1", "name": "<img src=x onerror=window.__pwn3=1>", "content": "# C", "modified": 3},
        {"id": "d1", "name": "wrong types", "content": {"x": 1}, "modified": "zzz"},
        "not even an object"]}
    path = os.path.join(tempfile.mkdtemp(), "evil.json")
    with open(path, "w") as fh:
        json.dump(evil, fh)
    driver.execute_script("window.alert = () => {}; window.confirm = () => true; Lib.open();"
                          "document.getElementById('lib-import').hidden = false;")
    driver.find_element(By.ID, "lib-import").send_keys(path)
    time.sleep(0.7)
    driver.execute_script("Lib.open();")
    n = len(driver.find_elements(By.CSS_SELECTOR, ".lib-item"))
    assert n >= 4, f"Library should list the 3 valid lectures plus existing ones, got {n}"
    for i in range(n):                      # hover and click every entry
        driver.execute_script("Lib.open();")
        name = driver.find_elements(By.CSS_SELECTOR, ".lib-item .lib-name")[i]
        ActionChains(driver).move_to_element(name).click(name).perform()
    assert not pwned(), f"Backup file ran code: {pwned()}"
    ids = driver.execute_script("return LIBRARY.lectures.map(l => l.id);")
    assert all(i.isalnum() for i in ids), f"Unsafe id stored: {ids}"
    driver.execute_script("Lib.close(); document.getElementById('lib-import').hidden = true;")

run_test("14. Security: malicious backup file", test_malicious_backup)

def test_malicious_lecture_text():
    attack = ("# <img src=x onerror=window.__pwn4=1>\\n"
              "<script>window.__pwn5=1</script>\\n"
              "[[<svg onload=window.__pwn6=1>; a&b, c<d]] || <b onclick=window.__pwn7=1>x</b>\\n"
              "{{<i>1</i>|2}} x^{<u>2</u>} ~~<s>z</s>~~")
    driver.execute_script(f"Ed.open(); document.getElementById('src').value = `{attack}`; Ed.close();"
                          "B.next(); B.next(); B.next();")
    assert not pwned(), f"Lecture text ran code: {pwned()}"
    tags = driver.execute_script("return [...document.querySelectorAll('#page img,#page script,#page svg,#page b,#page i,#page u,#page s')].length;")
    assert tags == 0, f"Lecture text created {tags} HTML elements"
    title = driver.find_element(By.ID, "title").text
    assert "<img" in title, f"Title should show the text literally, got {title!r}"
    cells = driver.execute_script("return [...document.querySelectorAll('.mx td')].map(td => td.textContent);")
    assert "a&b" in cells and "c<d" in cells, f"Matrix cells mangled by escaping: {cells}"

run_test("15. Security: malicious lecture text", test_malicious_lecture_text)

def test_csp_blocks_inline_script():
    csp = driver.execute_script("return document.querySelector('meta[http-equiv=Content-Security-Policy]')?.content || '';")
    script_src = next((d for d in csp.split(";") if d.strip().startswith("script-src")), "")
    assert script_src and "unsafe" not in script_src, f"script-src missing or weakened: {csp!r}"
    # Simulate a future bug that lets markup through: the browser must still refuse to run it
    driver.execute_script("document.getElementById('steps').insertAdjacentHTML('beforeend',"
                          "'<img src=\"data:,\" onerror=\"window.__pwn8=1\" onload=\"window.__pwn8=1\">');")
    time.sleep(0.3)
    driver.get_log('browser')               # the CSP violation report is expected here
    assert not pwned(), f"Inline handler ran despite CSP: {pwned()}"
    inline = driver.execute_script("return document.querySelectorAll('[onclick],[onchange],[oninput],[onload],[onerror]').length;")
    assert inline <= 1, "Inline event handlers found in the page; use data-do instead"

run_test("16. Security: CSP blocks inline script", test_csp_blocks_inline_script)

# ─────────────────────────────────────────────────────────────
# TEST 17: Install button
# ─────────────────────────────────────────────────────────────
def test_install_button():
    btn = driver.find_element(By.ID, "install")
    offered = driver.execute_script("return !!App.prompt;")   # Chrome may already have offered a real install
    assert btn.is_displayed() == offered, f"Install button visible={btn.is_displayed()} but browser offered install={offered}"
    # Stand-in for the browser's own install prompt
    driver.execute_script("""
      const e = new Event('beforeinstallprompt', {cancelable: true});
      e.prompt = () => { window.__prompted = true; };
      dispatchEvent(e);""")
    assert btn.is_displayed(), "Install button did not appear when install became available"
    btn.click()
    assert driver.execute_script("return window.__prompted === true;"), "Install button did not open the install prompt"
    assert not btn.is_displayed(), "Install button should hide after use"
    driver.execute_script("dispatchEvent(new Event('beforeinstallprompt')); dispatchEvent(new Event('appinstalled'));")
    assert not btn.is_displayed(), "Install button should hide once installed"

run_test("17. Install Button", test_install_button)

# ─────────────────────────────────────────────────────────────
# TEST 18: Help, tour and "write my own" from the welcome card
# ─────────────────────────────────────────────────────────────
def test_help_tour_write():
    body = driver.find_element(By.TAG_NAME, "body")
    body.send_keys("?")
    assert driver.execute_script("return document.getElementById('help').open;"), "'?' did not open the welcome card"
    before = driver.execute_script("return LIBRARY.lectures.length;")
    driver.find_element(By.CSS_SELECTOR, "#help [data-do='Help.tour']").click()
    assert driver.find_element(By.ID, "title").text == "Welcome to Board", "Tour did not start on its first slide"
    driver.execute_script("Help.open();")
    driver.find_element(By.CSS_SELECTOR, "#help [data-do='Help.tour']").click()
    tours = driver.execute_script("return LIBRARY.lectures.filter(l => l.name === 'Board tour').length;")
    assert tours <= 1, f"Tour was added again instead of reused ({tours} copies)"
    driver.execute_script("Help.open();")
    driver.find_element(By.CSS_SELECTOR, "#help [data-do='Help.write']").click()
    assert driver.execute_script("return !document.getElementById('editor').classList.contains('hidden');"), "Editor did not open"
    src = driver.execute_script("return document.getElementById('src').value;")
    assert src.startswith("time: 50") and "? A question" in src, "New lecture did not start from the template"
    assert driver.execute_script("return LIBRARY.lectures.length;") >= before + 1, "New lecture not added"
    driver.execute_script("Ed.close();")

run_test("18. Help, Tour and Write-My-Own", test_help_tour_write)

# Restore default lecture in library
driver.execute_script("""
  localStorage.clear();
  location.reload();
""")
time.sleep(1)

driver.quit()

print(json.dumps(test_results, indent=2))
passed = sum(r["status"] == "PASS" for r in test_results)
print(f"\n{passed}/{len(test_results)} passed")
sys.exit(0 if passed == len(test_results) else 1)
