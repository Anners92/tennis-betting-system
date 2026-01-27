// Tennis Betting System - Service Worker v2
// Caches pages for TRUE offline access

const CACHE_NAME = 'tennis-betting-v2';

// Pages to cache for offline
const PAGES_TO_CACHE = [
  '/',
  '/matches',
  '/bets',
  '/sync',
  '/add-bet',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

// Install - cache all pages immediately
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching pages for offline use');
      return cache.addAll(PAGES_TO_CACHE);
    }).then(() => {
      console.log('[SW] All pages cached');
      return self.skipWaiting();
    })
  );
});

// Activate - clean old caches and take control
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('[SW] Taking control of clients');
      return self.clients.claim();
    })
  );
});

// Fetch - Network first, fall back to cache
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip API requests - always go to network
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    // Try network first
    fetch(event.request)
      .then((networkResponse) => {
        // Got network response - cache it and return
        if (networkResponse && networkResponse.status === 200) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        // Network failed - try cache
        console.log('[SW] Network failed, serving from cache:', url.pathname);
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }

          // If exact match not found, try the base page
          // This handles navigation requests
          if (event.request.mode === 'navigate') {
            return caches.match('/').then((homeResponse) => {
              if (homeResponse) {
                return homeResponse;
              }
              // Last resort - return offline message
              return new Response(
                `<!DOCTYPE html>
                <html>
                <head>
                  <meta charset="UTF-8">
                  <meta name="viewport" content="width=device-width, initial-scale=1.0">
                  <title>Offline - Tennis Betting</title>
                  <style>
                    body {
                      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                      background: #1e1e2e;
                      color: white;
                      min-height: 100vh;
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      margin: 0;
                      padding: 20px;
                      text-align: center;
                    }
                    .container { max-width: 400px; }
                    h1 { color: #6366f1; margin-bottom: 20px; }
                    p { color: #888; line-height: 1.6; }
                    .btn {
                      display: inline-block;
                      margin-top: 20px;
                      padding: 12px 24px;
                      background: #6366f1;
                      color: white;
                      border-radius: 10px;
                      text-decoration: none;
                    }
                  </style>
                </head>
                <body>
                  <div class="container">
                    <h1>You're Offline</h1>
                    <p>The app needs to sync at least once while connected to your home WiFi.</p>
                    <p>Connect to WiFi and open the app to cache it for offline use.</p>
                    <a href="/" class="btn" onclick="window.location.reload()">Retry</a>
                  </div>
                </body>
                </html>`,
                {
                  headers: { 'Content-Type': 'text/html' },
                  status: 200
                }
              );
            });
          }

          return new Response('Offline', { status: 503 });
        });
      })
  );
});

// Listen for messages from the main app
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
