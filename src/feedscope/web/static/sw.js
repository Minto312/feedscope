// Minimal service worker. Its job is to make the app installable (a prerequisite
// for the Web Share Target); it deliberately does not cache article data, which
// must always come fresh from the server.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
