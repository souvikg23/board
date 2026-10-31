/* Board service worker: keeps the app working with no internet.
   Serves from cache instantly, then refreshes the cache in the background,
   so patchy classroom Wi-Fi never stalls a page load. Updates show on the next open.
   Bump VERSION to throw away every old cached file at once. */
const VERSION = 'board-v2';
const FILES = ['./', './index.html', './app.js', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png', './icons/maskable-512.png', './icons/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  const fresh = caches.open(VERSION).then(cache =>
    fetch(e.request).then(res => { if (res.ok) cache.put(e.request, res.clone()); return res; }));
  e.respondWith(caches.match(e.request, {ignoreSearch: true}).then(hit => hit || fresh));
  e.waitUntil(fresh.catch(() => {}));       // offline: keep serving the cached copy
});
