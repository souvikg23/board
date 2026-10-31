/* Board service worker: keeps the app working with no internet.
   Serves from cache instantly, then refreshes the cache in the background,
   so patchy classroom Wi-Fi never stalls a page load. Updates show on the next open.
   index.html loads app.js?v=<fingerprint>, so a page always runs the script it was built
   with: old page + old script, or new page + new script, never a mix.
   Bump VERSION to throw away every old cached file at once. */
const VERSION = 'board-v4';
const FILES = ['./', './index.html', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png', './icons/maskable-512.png', './icons/apple-touch-icon.png'];
const fresh = url => new Request(url, {cache: 'no-cache'});    // ask the server, never a stale HTTP cache

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(async cache => {
    await cache.addAll(FILES.map(fresh));
    const page = await (await cache.match('./')).text();
    const script = page.match(/src="(app\.js\?v=[\w-]+)"/);     // the exact script this page needs
    if (script) await cache.add(fresh(script[1]));
  }).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  const update = caches.open(VERSION).then(cache =>
    fetch(fresh(req.url)).then(res => { if (res.ok) cache.put(req, res.clone()); return res; }));
  e.respondWith(caches.match(req, {ignoreSearch: req.mode === 'navigate'}).then(hit => hit || update));
  e.waitUntil(update.catch(() => {}));       // offline: keep serving the cached copy
});
