/**
 * Vorlesen über "Pappagei" (deine Mac-App, neuronale Stimme) — und NUR darüber.
 * Kein Browser-TTS-Fallback: es soll ausschliesslich Pappagei lesen.
 *
 * Anbindung: die Seite spricht per window.postMessage mit der pappagei-
 * Browser-Erweiterung (content.js, Branch web-app-bridge / ab v0.4.0), die an
 * die lokale App weiterreicht (POST /speak, /speak/stop). Das umgeht CORS.
 * Ist die Erweiterung/App nicht da (z.B. iPad), passiert nichts ausser einer
 * Hinweis-Meldung.
 */

export const tts = $state({
  aktiv: false,
  label: "",
  fehler: "", // gesetzt wenn Pappagei nicht erreichbar war
});

const _ackWaiter = new Map();
let _bridgeId = 0;

if (typeof window !== "undefined") {
  window.addEventListener("message", (e) => {
    if (e.source !== window) return;
    const d = e.data;
    if (!d || d.type !== "pappagei-ack") return;
    const w = _ackWaiter.get(d.id);
    if (w) {
      _ackWaiter.delete(d.id);
      w(d);
    }
  });
}

function _bridge(action, extra, timeoutMs = 1200) {
  return new Promise((resolve) => {
    if (typeof window === "undefined") {
      resolve(null);
      return;
    }
    const id = ++_bridgeId;
    let fertig = false;
    const t = setTimeout(() => {
      if (!fertig) {
        fertig = true;
        _ackWaiter.delete(id);
        resolve(null);
      }
    }, timeoutMs);
    _ackWaiter.set(id, (d) => {
      if (!fertig) {
        fertig = true;
        clearTimeout(t);
        resolve(d);
      }
    });
    try {
      window.postMessage({ type: "pappagei", action, id, ...(extra || {}) }, "*");
    } catch {
      /* egal */
    }
  });
}

/**
 * Liest Text über Pappagei vor. Gibt true zurück, wenn Pappagei übernommen hat,
 * sonst false (und setzt tts.fehler).
 */
export async function sprich(text, label = "") {
  const t = (text || "").trim();
  tts.fehler = "";
  if (!t) return false;
  const d = await _bridge("speak", { text: t.slice(0, 49000) });
  if (d && d.ok) {
    tts.aktiv = true;
    tts.label = label;
    return true;
  }
  tts.aktiv = false;
  tts.label = "";
  tts.fehler =
    "Pappagei nicht erreichbar – läuft die App und ist die Erweiterung aktuell (≥ 0.4.0)?";
  return false;
}

export function stop() {
  _bridge("stop", {}, 500);
  tts.aktiv = false;
  tts.label = "";
  tts.fehler = "";
}

/** Prüft, ob die Pappagei-Erweiterung/App erreichbar ist. */
export async function pruefeVerfuegbar() {
  const d = await _bridge("ping", {}, 1000);
  return !!(d && d.ok);
}
