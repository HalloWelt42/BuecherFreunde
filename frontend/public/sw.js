// Hülle der App ohne Netz: Seite und gebaute Dateien liegen vor, Daten nie. Die Seite kommt zuerst vom Server (so gilt jede neue
// Fassung sofort), aus dem Speicher nur, wenn er nicht antwortet. Gebaute Dateien tragen ihre Prüfsumme im Namen und ändern sich nie.
const FASSUNG = "__FASSUNG__";
const HUELLE = `huelle-${FASSUNG}`;
const BAU = `bau-${FASSUNG}`;
const WARTEN_MS = 4000;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(HUELLE).then((c) => c.addAll(["/", "/site.webmanifest", "/favicon.svg"])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((namen) => Promise.all(namen.filter((n) => n !== HUELLE && n !== BAU).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

async function seite(anfrage) {
  const abbruch = new AbortController();
  const uhr = setTimeout(() => abbruch.abort(), WARTEN_MS);
  try {
    const antwort = await fetch(anfrage, { signal: abbruch.signal });
    if (antwort.ok) await (await caches.open(HUELLE)).put("/", antwort.clone());
    return antwort;
  } catch {
    return (await caches.match("/")) ?? Response.error();
  } finally {
    clearTimeout(uhr);
  }
}

async function gebaut(anfrage) {
  const da = await caches.match(anfrage);
  if (da) return da;
  const antwort = await fetch(anfrage);
  if (antwort.ok) await (await caches.open(BAU)).put(anfrage, antwort.clone());
  return antwort;
}

self.addEventListener("fetch", (e) => {
  const ziel = new URL(e.request.url);
  if (e.request.method !== "GET" || ziel.origin !== location.origin || ziel.pathname.startsWith("/api/")) return;
  if (e.request.mode === "navigate") e.respondWith(seite(e.request));
  else if (ziel.pathname.startsWith("/assets/")) e.respondWith(gebaut(e.request));
});
