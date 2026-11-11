{% autoescape off %}/* Service worker do AutoCheck. Guarda somente arquivos públicos e a página "sem conexão".
   Telas, fotos e relatórios contêm dados pessoais e nunca entram no cache. */
const CACHE_NAME = "{{ cache_name }}";
const OFFLINE_URL = {{ offline_url }};
const STATIC_PREFIX = {{ static_prefix }};
const PRECACHE = {{ precache }};

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
    return;
  }
  if (url.pathname.startsWith(STATIC_PREFIX)) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      }))
    );
  }
  // Demais pedidos (fotos, PDFs, consultas) seguem direto para a rede, sem cache.
});
{% endautoescape %}
