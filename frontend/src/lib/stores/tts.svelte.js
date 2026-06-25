/**
 * Vorlese-Steuerung ("Papagei") über die Web Speech API (speechSynthesis).
 * Läuft komplett im Browser/offline, funktioniert auch auf dem iPad.
 *
 * Lange Texte werden in Sätze/Häppchen zerlegt und verkettet, da iOS-Safari
 * lange Utterances abschneidet. Stop bricht alles ab; Pause/Weiter steuert.
 */

const synth = typeof window !== "undefined" ? window.speechSynthesis : null;

export const tts = $state({
  verfuegbar: !!synth,
  aktiv: false,
  pausiert: false,
  label: "",
});

let _queue = [];
let _index = 0;
let _stimme = null;
let _rate = 0.95;
let _generation = 0; // entwertet alte onend-Callbacks nach stop()/neuem sprich()

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
  // Stimmen laden teils asynchron nach
  if (typeof synth.addEventListener === "function") {
    synth.addEventListener("voiceschanged", () => {
      _stimme = _waehleStimme();
    });
  }
}

// iOS-Safari spricht erst nach einer Nutzergeste. Beim ersten Klick/Touch
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

/** Text in vorlesbare Häppchen zerlegen (an Satzzeichen, lange Stücke teilen). */
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

function _sprichNaechstes(gen) {
  if (!synth || gen !== _generation) return;
  if (_index >= _queue.length) {
    stop();
    return;
  }
  const u = new SpeechSynthesisUtterance(_queue[_index]);
  u.lang = "de-DE";
  u.rate = _rate;
  if (_stimme) u.voice = _stimme;
  u.onend = () => {
    if (gen !== _generation) return;
    _index++;
    _sprichNaechstes(gen);
  };
  u.onerror = () => {
    if (gen !== _generation) return;
    _index++;
    _sprichNaechstes(gen);
  };
  synth.speak(u);
}

/** Startet das Vorlesen eines Textes. label z.B. "Seite", "Kapitel". */
export function sprich(text, label = "") {
  if (!synth) return;
  _queue = _haeppchen(text);
  _index = 0;
  if (_queue.length === 0) return;
  _generation++;
  const gen = _generation;
  tts.aktiv = true;
  tts.pausiert = false;
  tts.label = label;
  try {
    synth.cancel();
  } catch {
    /* egal */
  }
  // Kleiner Versatz: iOS verschluckt sonst die erste Utterance direkt nach cancel.
  setTimeout(() => _sprichNaechstes(gen), 90);
}

export function stop() {
  if (!synth) return;
  _generation++;
  _queue = [];
  _index = 0;
  tts.aktiv = false;
  tts.pausiert = false;
  tts.label = "";
  try {
    synth.cancel();
  } catch {
    /* egal */
  }
}

export function pause() {
  if (!synth || !tts.aktiv) return;
  try {
    synth.pause();
    tts.pausiert = true;
  } catch {
    /* egal */
  }
}

export function weiter() {
  if (!synth || !tts.aktiv) return;
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
