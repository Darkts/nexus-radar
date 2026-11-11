const CACHE_NAME = 'nexus-v8-clean';
const ASSETS_TO_CACHE = [
  './manifest.json',
  './assets/icon.svg'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE)).catch(() => {})
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const reqUrl = event.request.url;
  // Network-First pour HTML, JSON et données dynamiques afin d'éviter tout cache figé
  if (
    event.request.mode === 'navigate' ||
    reqUrl.endsWith('.html') ||
    reqUrl.endsWith('/') ||
    reqUrl.includes('annonces.json') ||
    reqUrl.includes('config.json')
  ) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || '⚡ Nexus Radar V8 : Nouvelle Pépite !';
  const options = {
    body: data.message || "Une nouvelle offre vient d'être détectée.",
    icon: './assets/icon.svg',
    badge: './assets/icon.svg',
    data: { url: data.click || './index.html' },
    vibrate: [200, 100, 200]
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || './index.html';
  event.waitUntil(clients.openWindow(url));
});
