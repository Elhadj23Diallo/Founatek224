// ── FOUNATEK NEXUS — Service Worker ──────────────────────────
const CACHE_NAME = 'founatek-nexus-v2';

const CACHE_URLS = [
  '/air-quality/',
  '/static/manifest.json',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://cdn.jsdelivr.net/npm/chart.js',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('FOUNATEK NEXUS — Cache installé');
      return cache.addAll(CACHE_URLS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Ne jamais mettre en cache le shop, admin, login, panier, commandes
  if (url.pathname.startsWith('/shop/') ||
      url.pathname.startsWith('/admin/') ||
      url.pathname.startsWith('/accounts/') ||
      url.pathname.startsWith('/panier/') ||
      url.pathname.startsWith('/commandes/') ||
      url.pathname.startsWith('/fidelite/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // API et air-quality → toujours réseau (données temps réel)
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/air-quality/') ||
      url.pathname.startsWith('/alert/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match('/air-quality/');
      })
    );
    return;
  }

  // Fichiers statiques → cache en priorité
  event.respondWith(
    caches.match(event.request).then(cached => {
      return cached || fetch(event.request).then(response => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      });
    })
  );
});
