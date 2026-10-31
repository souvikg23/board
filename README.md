# Board

Offline lecture board. Installs as an app on PC (Chrome/Edge) and phones (Android, iOS).

**Live:** https://souvikg23.github.io/board/

## Put it online once (free, 5 min)
1. Create a public GitHub repo, upload everything in this folder (keep `icons/`).
2. Repo → Settings → Pages → Deploy from branch → `main` / root → Save.
3. Open `https://<username>.github.io/<repo>/`.

## Install
Press **⬇ Install app** in Board's sidebar (Chrome, Edge, Brave, Android; on iPhone/iPad it shows the steps). Or:
- PC (Chrome/Edge/Brave): install icon at the right of the address bar.
- Android (Chrome): menu → Add to home screen / Install app.
- iPhone/iPad (Safari): Share → Add to Home Screen.

Open it once while online. After that it runs with no internet, and everything (lectures, settings)
stays on that device. Board asks the browser to keep that storage permanently, so it isn't cleared when space runs low.

## Writing lectures
Press **Edit lecture** (or E). Lectures are plain text; the format guide is inside the editor.
Your lecture is kept on that device. Use **Save file** / **Open file** to move lectures between devices or share them.

## Updating the app itself
Code lives in `app.js`, layout and styles in `index.html`. Edit, push, done:
installed copies fetch the new version in the background and show it on the next open.
Bump `VERSION` in `sw.js` only if you add or rename files.

Double-clicking `index.html` on a PC still works offline without installing.

## Tests
Every push and pull request runs these automatically (GitHub → **Actions** tab):
the functional tests, attack tests for the known injection paths, and a CodeQL security scan.
To run the tests locally:
```
python -m http.server 8080          # in this folder
python tests/run_full_test_suite.py # needs: pip install selenium, plus Chrome
```
Pass a different URL as the first argument to test the live site.
