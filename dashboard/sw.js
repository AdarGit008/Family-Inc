// Family inc. dashboard — minimal service worker.
// Caches the app shell so the dashboard opens offline; data still tries network first.

const SHELL_CACHE = 'family-inc-shell-v2'; // v2: M2 — Settings/UserMap identity, write-contract fixes
const SHELL_FILES = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './config.js',
  './manifest.webmanifest',
  './icon.svg',
  './mock_data.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL_CACHE).then(c => c.addAll(SHELL_FILES)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== SHELL_CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // Never cache Google API calls.
  if (url.host.includes('googleapis.com') || url.host.includes('accounts.google.com')) return;
  // Cache-first for our own shell, network-first as fallback for everything else.
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
      if (resp.ok && e.request.method === 'GET' && url.origin === location.origin) {
        const clone = resp.clone();
        caches.open(SHELL_CACHE).then(c => c.put(e.request, clone)).catch(() => {});
      }
      return resp;
    }).catch(() => cached))
  );
});
