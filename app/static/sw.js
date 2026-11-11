// Service worker van de WTC Chatbot (PWA-installatie). Zie issue #35 en docs/adr/0007.
//
// Privacy-afspraak (hard): /chat, /feedback en /healthz worden NOOIT gecached.
// Daar zit vraag/antwoord in; alleen de app-shell mag lokaal worden bewaard.
"use strict";

var CACHE = "wtchat-shell-v16"; // bij elke wijziging van de shell: versie ophogen
var SHELL = [
  "/",
  "/index.html",
  "/debug.js",
  "/viewport.js",
  "/manifest.webmanifest",
  "/icons/favicon-32.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable-512.png",
  "/icons/apple-touch-icon.png",
  "/wielie.jpg",
  "/Achtergrond%2016-9.jpg"
];

var NEVER_CACHE = ["/chat", "/feedback", "/healthz"];

function isNeverCache(pathname) {
  return NEVER_CACHE.some(function (p) {
    return pathname === p || pathname.indexOf(p + "/") === 0;
  });
}

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) { return cache.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (key) {
        if (key !== CACHE) { return caches.delete(key); }
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var url = new URL(event.request.url);

  // Alleen GET van onze eigen origin afhandelen; de rest gaat sowieso via netwerk.
  if (event.request.method !== "GET") { return; }
  if (url.origin !== location.origin) { return; }
  // Privacy: API-endpoints altijd via netwerk, nooit uit de cache.
  if (isNeverCache(url.pathname)) { return; }

  // Navigaties: network-first, fallback op de gecachte shell (offline start).
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).then(function (resp) {
        var copy = resp.clone();
        caches.open(CACHE).then(function (cache) { cache.put("/index.html", copy); });
        return resp;
      }).catch(function () {
        return caches.match("/index.html");
      })
    );
    return;
  }

  // Overige static assets: cache-first, dan netwerk (en bewaar in cache).
  event.respondWith(
    caches.match(event.request).then(function (hit) {
      return hit || fetch(event.request).then(function (resp) {
        if (resp.ok) {
          var copy = resp.clone();
          caches.open(CACHE).then(function (cache) { cache.put(event.request, copy); });
        }
        return resp;
      });
    })
  );
});
