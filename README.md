# Board

Offline lecture board. Installs as an app on PC (Chrome/Edge) and phones (Android, iOS).

**Live:** https://souvikg23.github.io/board/

## Put it online once (free, 5 min)
1. Create a public GitHub repo, upload everything in this folder (keep `icons/`).
2. Repo → Settings → Pages → Deploy from branch → `main` / root → Save.
3. Open `https://<username>.github.io/<repo>/`.

## Install
- PC (Chrome/Edge): install icon at the right of the address bar.
- Android (Chrome): menu → Add to home screen / Install app.
- iPhone/iPad (Safari): Share → Add to Home Screen.

Open it once while online. After that it runs with no internet.

## Writing lectures
Press **Edit lecture** (or E). Lectures are plain text; the format guide is inside the editor.
Your lecture is kept on that device. Use **Save file** / **Open file** to move lectures between devices or share them.

## Updating the app itself
Edit `index.html`, then change `VERSION` in `sw.js` (e.g. `board-v1` → `board-v2`) and push.
Installed copies pick it up the next time they open while online.

Double-clicking `index.html` on a PC still works offline without installing.

## Tests
```
python -m http.server 8080          # in this folder
python tests/run_full_test_suite.py # needs: pip install selenium, plus Chrome
```
Pass a different URL as the first argument to test the live site.
