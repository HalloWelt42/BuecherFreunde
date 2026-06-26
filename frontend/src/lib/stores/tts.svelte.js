/**
 * Vorlese-Steuerung. Bevorzugt die "Pappagei"-App (neuronale Stimme auf dem
 * Mac) über die Browser-Extension; ist sie nicht erreichbar (z.B. iPad oder
 * App aus), wird die Web Speech API als Fallback genutzt.
 *
 * Pappagei-Anbindung: per window.postMessage spricht die Seite mit der
 * pappagei-Extension (content.js), die an die lokale App weiterreicht. Das
 * umgeht CORS/Netzwerksperren komplett.
 */

const synth = typeof window !== "undefined" ? window.speechSynthesis : null;

export const tts = $state({
  verfuegbar: typeof window !== "undefined",
  aktiv: false,
  pausiert: false,
  label: "",
  modus: null, // "pappagei" | "webspeech" | null
});

// ===================== Pappagei-Brücke (Browser-Extension) =================

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

function _bridge(action, extra, timeoutMs = 800) {
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

async function _pappageiSprich(text) {
  const d = await _bridge("speak", { text: text.slice(0, 49000) });
  return !!(d && d.ok);
}

function _pappageiStop() {
  _bridge("stop", {}, 300);
}

// ===================== Web Speech API (Fallback) ===========================

let _queue = [];
let _index = 0;
let _stimme = null;
let _rate = 0.95;
let _generation = 0;

function _waehleStimme() {
  if (!synth) return null;
  const stimmen = synth.getVoices() || [];
  return (
    stimmen.find((v) => v.lang && v.lang.toLowerCase().startsWith("de")) ||
    stimmen[0] ||
    null
  );
}

if (synth) {
  _stimme = _waehleStimme();
  if (typeof synth.addEventListener === "function") {
    synth.addEventListener("voiceschanged", () => {
      _stimme = _waehleStimme();
    });
  }
}

// iOS-Safari spricht erst nach einer Nutzergeste -> beim ersten Klick/Touch
// einmalig eine stille Utterance abspielen, um speechSynthesis zu entsperren.
let _entsperrt = false;
function _entsperre() {
  if (_entsperrt || !synth) return;
  _entsperrt = true;
  try {
    const u = new SpeechSynthesisUtterance(" ");
    u.volume = 0;
    synth.speak(u);
    synth.cancel();
  } catch {
    /* egal */
  }
}
if (synth && typeof document !== "undefined") {
  const opts = { once: true, capture: true };
  document.addEventListener("pointerdown", _entsperre, opts);
  document.addEventListener("touchend", _entsperre, opts);
  document.addEventListener("click", _entsperre, opts);
}

function _haeppchen(text) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  if (!clean) return [];
  const saetze = clean.match(/[^.!?…]+[.!?…]*\s*/g) || [clean];
  const out = [];
  for (let s of saetze) {
    s = s.trim();
    while (s.length > 220) {
      let cut = s.lastIndexOf(" ", 220);
      if (cut < 80) cut = 220;
      out.push(s.slice(0, cut).trim());
      s = s.slice(cut).trim();
    }
    if (s) out.push(s);
  }
  return out;
}

function _webNaechstes(gen) {
  if (!synth || gen !== _generation) return;
  if (_index >= _queue.length) {
    _webStop();
    if (tts.modus === "webspeech") {
      tts.aktiv = false;
      tts.pausiert = false;
      tts.label = "";
      tts.modus = null;
    }
    return;
  }
  const u = new SpeechSynthesisUtterance(_queue[_index]);
  u.lang = "de-DE";
  u.rate = _rate;
  if (_stimme) u.voice = _stimme;
  u.onend = () => {
    if (gen !== _generation) return;
    _index++;
    _webNaechstes(gen);
  };
  u.onerror = () => {
    if (gen !== _generation) return;
    _index++;
    _webNaechstes(gen);
  };
  synth.speak(u);
}

function _webSprich(text, label) {
  if (!synth) return;
  _queue = _haeppchen(text);
  _index = 0;
  if (_queue.length === 0) return;
  _generation++;
  const gen = _generation;
  tts.aktiv = true;
  tts.pausiert = false;
  tts.label = label;
  tts.modus = "webspeech";
  try {
    synth.cancel();
  } catch {
    /* egal */
  }
  setTimeout(() => _webNaechstes(gen), 90);
}

function _webStop() {
  _generation++;
  _queue = [];
  _index = 0;
  if (!synth) return;
  try {
    synth.cancel();
  } catch {
    /* egal */
  }
}

// ===================== Öffentliche API =====================================

/** Startet das Vorlesen. label z.B. "Seite", "Kapitel", "Ganzes Buch". */
export async function sprich(text, label = "") {
  const t = (text || "").trim();
  stop();
  if (!t) return;
  // 1) Pappagei (neuronale Stimme über die Mac-App)
  if (await _pappageiSprich(t)) {
    tts.aktiv = true;
    tts.pausiert = false;
    tts.label = label;
    tts.modus = "pappagei";
    return;
  }
  // 2) Fallback: Web Speech API
  _webSprich(t, label);
}

export function stop() {
  _pappageiStop();
  _webStop();
  tts.aktiv = false;
  tts.pausiert = false;
  tts.label = "";
  tts.modus = null;
}

export function pause() {
  if (tts.modus !== "webspeech" || !synth || !tts.aktiv) return;
  try {
    synth.pause();
    tts.pausiert = true;
  } catch {
    /* egal */
  }
}

export function weiter() {
  if (tts.modus !== "webspeech" || !synth || !tts.aktiv) return;
  try {
    synth.resume();
    tts.pausiert = false;
  } catch {
    /* egal */
  }
}

export function setRate(r) {
  _rate = r;
}
