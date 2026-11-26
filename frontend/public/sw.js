// Hülle der App ohne Netz. Die Seite kommt zuerst vom Server (so gilt jede neue Fassung sofort), aus dem Speicher nur, wenn er
// nicht antwortet. Gebaute Dateien tragen ihre Prüfsumme im Namen und ändern sich nie; die Hülle und der Leser mit allen
// Formaten (pdf.js samt Worker, foliate-js, Textleser) liegen vorab bereit, den Vorrat setzt der Bau ein (vite.config.js).
//
// Lesestoff, nur wenn das Gerät es ausdrücklich erlaubt (Einstellungen, Verbindungen, Ohne Netz lesen; Vorgabe aus): was der
// Leser zu einem Buch holt (Angaben, Datei, Markierungen, Notizen, Etiketten, Textseiten), kommt zuerst vom Server und wird
// gemerkt; ohne Netz geht ein schon geöffnetes Buch so wieder auf. Höchstens BUECHER Bücher und zusammen HOECHSTENS_BYTE,
// die ältesten gehen zuerst; beim Abmelden ist alles weg. Ohne Netz und ohne gemerktes Buch sagt eine Antwort, warum.
// Die Seite spricht über Nachrichten mit diesem Dienst (src/lib/stand/lesestoff.svelte.ts).
const FASSUNG = "__FASSUNG__";
const VORRAT = "__VORRAT__";
const HUELLE = `huelle-${FASSUNG}`;
const BAU = `bau-${FASSUNG}`;
const LESESTOFF = "lesestoff";
const VERZEICHNIS = "/__lesestoff";
const BUECHER = 5;
const HOECHSTENS_BYTE = 500 * 1000 * 1000; // dezimal, wie die Oberfläche Größen nennt
const WARTEN_MS = 4000;
const ZUM_BUCH = /^\/api\/books\/(\d+)(?:\/(?:file|highlights|notes|labels|textseiten))?$/;
const OHNE_NETZ = {
  aus: "Ohne Netz geht dieses Buch nicht auf. Damit zuletzt geöffnete Bücher auch so aufgehen: Einstellungen, Verbindungen, Ohne Netz lesen.",
  an: "Ohne Netz geht dieses Buch nicht auf: es liegt nicht auf diesem Gerät.",
};

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    await (await caches.open(HUELLE)).addAll(["/", "/site.webmanifest", "/favicon.svg"]);
    // Was schon in einer älteren Fassung lag, wird übernommen, nur Neues kommt über das Netz; Fehlendes hält nichts auf
    const bau = await caches.open(BAU);
    await Promise.allSettled((Array.isArray(VORRAT) ? VORRAT : []).map(async (weg) => {
      if (await bau.match(weg)) return;
      const da = await caches.match(weg);
      await (da ? bau.put(weg, da) : bau.add(weg));
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((namen) => Promise.all(namen.filter((n) => ![HUELLE, BAU, LESESTOFF].includes(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

/** Vom Server; mit `frist` gilt eine Uhr bis zum Kopf der Antwort, nie für ihren Inhalt */
async function vomServer(anfrage, frist) {
  if (!frist) return fetch(anfrage);
  const abbruch = new AbortController();
  const uhr = setTimeout(() => abbruch.abort(), frist);
  try {
    return await fetch(anfrage, { signal: abbruch.signal });
  } finally {
    clearTimeout(uhr);
  }
}

async function seite(anfrage) {
  try {
    const antwort = await vomServer(anfrage, WARTEN_MS);
    if (antwort.ok) await (await caches.open(HUELLE)).put("/", antwort.clone());
    return antwort;
  } catch {
    return (await caches.match("/")) ?? Response.error();
  }
}

/**
 * Eine Bereichsanfrage bekommt genau ihr Stück (206), auch wenn die ganze Datei aus dem Speicher kommt: Safari fragt Töne
 * zuerst mit "bytes=0-1" an und spielt sie nur mit einer Teilantwort (sonst bleibt etwa das Schnurren der Katze stumm), pdf.js
 * fragt Bücher in Bereichen an. Ohne Bereich, mit einem Bereich, den diese Regel nicht kennt, oder wenn die Antwort schon ein
 * Stück ist, bleibt sie, wie sie ist.
 */
async function stueck(anfrage, ganz) {
  const bereich = /^bytes=(\d+)-(\d*)$/.exec(anfrage.headers.get("range") ?? "");
  if (!bereich || ganz.status !== 200) return ganz;
  const daten = await ganz.blob();
  const von = Number(bereich[1]);
  if (von >= daten.size) return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${daten.size}` } });
  const bis = Math.min(bereich[2] ? Number(bereich[2]) : daten.size - 1, daten.size - 1);
  return new Response(daten.slice(von, bis + 1), {
    status: 206,
    headers: { "Content-Type": ganz.headers.get("content-type") ?? "", "Content-Range": `bytes ${von}-${bis}/${daten.size}`, "Content-Length": String(bis - von + 1), "Accept-Ranges": "bytes" },
  });
}

async function gebaut(anfrage) {
  const da = await caches.match(anfrage);
  if (da) return stueck(anfrage, da);
  const antwort = await fetch(anfrage);
  // Gemerkt wird nur die ganze Datei; ein Stück (206) nimmt der Speicher nicht an, die Antwort ginge sonst verloren
  if (antwort.status === 200) await (await caches.open(BAU)).put(anfrage, antwort.clone());
  return stueck(anfrage, antwort);
}

// --- Lesestoff ---------------------------------------------------------------------------------------------------------

// Ein Schritt nach dem anderen am Verzeichnis, sonst ginge beim gleichzeitigen Merken ein Eintrag verloren
let kette = Promise.resolve();
const nacheinander = (schritt) => (kette = kette.then(schritt, schritt));

async function verzeichnis(speicher) {
  const v = await (await speicher.match(VERZEICHNIS))?.json().catch(() => null);
  return { an: v?.an === true, buecher: v?.buecher ?? {} };
}

const schreibe = (speicher, v) => speicher.put(VERZEICHNIS, new Response(JSON.stringify(v), { headers: { "Content-Type": "application/json" } }));
const bytesVon = (buch) => Object.values(buch.teile ?? {}).reduce((a, b) => a + b, 0);

async function vergiss(speicher, v, nummern) {
  for (const eintrag of await speicher.keys()) {
    const m = ZUM_BUCH.exec(new URL(eintrag.url).pathname);
    if (m && nummern.includes(m[1])) await speicher.delete(eintrag);
  }
  for (const n of nummern) delete v.buecher[n];
}

/** Die ältesten Bücher gehen, bis Zahl und Platz wieder passen; das gerade geholte bleibt */
async function halteGrenzen(speicher, v, jetzt) {
  const alt = Object.keys(v.buecher).filter((n) => n !== jetzt).sort((a, b) => v.buecher[a].zeit - v.buecher[b].zeit);
  const weg = [];
  const zahl = () => Object.keys(v.buecher).length - weg.length;
  const platz = () => Object.entries(v.buecher).filter(([n]) => !weg.includes(n)).reduce((a, [, b]) => a + bytesVon(b), 0);
  while (alt.length && (zahl() > BUECHER || platz() > HOECHSTENS_BYTE)) weg.push(alt.shift());
  if (weg.length) await vergiss(speicher, v, weg);
}

function merke(weg, antwort, buch) {
  return nacheinander(async () => {
    const speicher = await caches.open(LESESTOFF);
    const v = await verzeichnis(speicher);
    if (!v.an) return;
    const bytes = Number(antwort.headers.get("content-length")) || (await antwort.clone().blob()).size;
    if (bytes > HOECHSTENS_BYTE) return;
    const eintrag = v.buecher[buch] ?? { titel: "", teile: {} };
    if (new URL(weg).pathname === `/api/books/${buch}`) eintrag.titel = (await antwort.clone().json().catch(() => ({}))).title ?? eintrag.titel;
    try {
      await speicher.put(weg, antwort);
    } catch {
      return; // Speicher des Geräts voll: dann bleibt es beim Netz
    }
    v.buecher[buch] = { ...eintrag, zeit: Date.now(), teile: { ...eintrag.teile, [weg]: bytes } };
    await halteGrenzen(speicher, v, buch);
    await schreibe(speicher, v);
  }).catch(() => {});
}

/** Aus dem Gemerkten, auch ein Stück der Datei (pdf.js fragt nach Bereichen) */
async function gemerkt(anfrage) {
  const da = await (await caches.open(LESESTOFF)).match(anfrage.url);
  return da ? stueck(anfrage, da) : null;
}

async function ohneNetz(anfrage) {
  const v = await verzeichnis(await caches.open(LESESTOFF));
  return (await gemerkt(anfrage)) ?? new Response(JSON.stringify({ detail: OHNE_NETZ[v.an ? "an" : "aus"] }), { status: 503, headers: { "Content-Type": "application/json" } });
}

async function lesestoff(e, buch) {
  const anfrage = e.request;
  // Liegt das Buch schon da, wartet niemand lange auf ein zähes Netz; sonst bleibt nur das Netz, so lange es braucht
  const da = await (await caches.open(LESESTOFF)).match(anfrage.url);
  try {
    const antwort = await vomServer(anfrage, da ? WARTEN_MS : 0);
    if (antwort.status >= 500 && da) return ohneNetz(anfrage);
    if (antwort.status === 200 && !anfrage.headers.has("range")) e.waitUntil(merke(anfrage.url, antwort.clone(), buch));
    return antwort;
  } catch {
    return ohneNetz(anfrage);
  }
}

/** Was die Seite unter Einstellungen zeigt: Wahl, Bücher mit Titel und Platz, Grenzen */
async function stand() {
  const v = await verzeichnis(await caches.open(LESESTOFF));
  const buecher = Object.entries(v.buecher).map(([id, b]) => ({ id: Number(id), titel: b.titel, bytes: bytesVon(b), zeit: b.zeit })).sort((a, b) => b.zeit - a.zeit);
  return { an: v.an, buecher, bytes: buecher.reduce((a, b) => a + b.bytes, 0), grenzen: { buecher: BUECHER, bytes: HOECHSTENS_BYTE } };
}

async function leere(an) {
  await nacheinander(async () => {
    const speicher = await caches.open(LESESTOFF);
    const v = await verzeichnis(speicher);
    await vergiss(speicher, v, Object.keys(v.buecher));
    await schreibe(speicher, { ...v, an: an ?? v.an });
  });
}

self.addEventListener("message", (e) => {
  const art = e.data?.art;
  const antworte = (tun) => e.waitUntil(tun().then(stand).then((s) => e.ports[0]?.postMessage(s)).catch(() => e.ports[0]?.postMessage(null)));
  if (art === "abgemeldet") antworte(() => leere());
  else if (art === "lesestoff") antworte(async () => {});
  else if (art === "lesestoff-leeren") antworte(() => leere());
  else if (art === "lesestoff-an") {
    antworte(async () => {
      if (!e.data.an) return leere(false);
      await nacheinander(async () => {
        const speicher = await caches.open(LESESTOFF);
        await schreibe(speicher, { ...(await verzeichnis(speicher)), an: true });
      });
    });
  }
});

self.addEventListener("fetch", (e) => {
  const ziel = new URL(e.request.url);
  if (e.request.method !== "GET" || ziel.origin !== location.origin) return;
  const buch = ziel.searchParams.has("herunterladen") ? null : ZUM_BUCH.exec(ziel.pathname);
  if (buch) e.respondWith(lesestoff(e, buch[1]));
  else if (ziel.pathname.startsWith("/api/")) return;
  else if (e.request.mode === "navigate") e.respondWith(seite(e.request));
  else if (ziel.pathname.startsWith("/assets/")) e.respondWith(gebaut(e.request));
});
