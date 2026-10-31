# Board

A blank board for teaching. Opens instantly, works with no internet, no login.
Installs as an app on PC (Chrome, Edge, Brave) and phones (Android, iPhone, iPad).

**Live:** https://souvikg23.github.io/board/

## What it does
- **Draw** with a mouse, stylus or finger: four colours, three sizes, a duster, and a **Line** tool
  (or Shift+drag) that snaps level/upright. **Pen** switches off so you can point without marking.
  Several people can draw at once (smart boards). Undo/redo covers everything, even a cleared page.
  With a stylus, a resting palm doesn't draw.
- **Pages**: + Page for a fresh board; flip with ◀ ▶, the arrow keys or a presentation clicker
  (moving past the last page gives you a new one).
- **Save & share**: Save turns every page into one picture (on phones it opens the Share sheet, e.g. WhatsApp).
  **New board** (in the ⋯ menu) starts fresh and saves the old board as a picture first.
- On 4K smart boards the toolbar and ink are scaled up automatically.
- Plain, grid or ruled background · lecture clock · chalkboard or whiteboard
  (colours re-ink to suit, so white chalk never disappears on a whiteboard).
- Your board stays on this device and survives closing the tab. Board asks the browser to keep that storage
  permanently, so it isn't cleared when space runs low.

Press **?** in the app for the keyboard shortcuts.

## Install
Press **⬇ Install app** in the toolbar (on iPhone/iPad it shows the steps), or use the install icon in the address bar.
Open it once while online; after that it runs with no internet.

## Updating the app
Code lives in `app.js`, layout and styles in `index.html`. Installed copies fetch new versions in
the background and show them on the next open.

After editing `app.js`, update its fingerprint in `index.html` (`<script src="app.js?v=…">`).
The tests fail and print the exact value if you forget. The fingerprint guarantees a page only ever
runs the script it was built with, even from a stale cache.
Bump `VERSION` in `sw.js` only if you add or rename files.

The earlier slide-presenter version is kept on the `presenter` branch.

## Tests
Every push and pull request runs these automatically (GitHub → **Actions** tab):
the functional tests, attack tests against tampered saved data, and a CodeQL security scan.
To run the tests locally:
```
python -m http.server 8080          # in this folder
python tests/run_full_test_suite.py # needs: pip install selenium, plus Chrome
```
Pass a different URL as the first argument to test the live site.
