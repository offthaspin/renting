const CACHE_NAME = "rentana-cache-v1";
const urlsToCache = [
  "/", 
  "/static/css/styles.css",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

// Install Service Worker and cache core files
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log("✅ Caching app shell");
      return cache.addAll(urlsToCache);
    })
  );
});

// Activate and clean up old caches
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(key => key !== CACHE_NAME)
            .map(key => caches.delete(key))
      )
    )
  );
  console.log("🚀 Service Worker activated");
});

// Fetch: serve cached files when offline
self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
      .catch(() => caches.match("/"))
  );
});
