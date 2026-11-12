/* Service worker mínimo: hace la app instalable y deja abrir la pantalla
   aunque la red tarde. Nunca toca /api: las descargas siempre van al servidor. */
const CACHE = "67dl-shell-v2";
const SHELL = ["./", "style.css?v=5", "app.js?v=5", "favicon.svg", "icons/icon-192.png"];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL))
      .catch(() => {}) // si algo falla no bloquea la instalación
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;

  // Primero la red (así siempre ves la versión nueva); si falla, la copia guardada
  event.respondWith(
    fetch(req)
      .then(res => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then(hit => hit || caches.match("./")))
  );
});
