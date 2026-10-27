/**
 * Einstellungen der Textansicht eines PDF, je Gerät gemerkt: ob sie an ist, Schriftgröße und Farbthema.
 * Die Farbthemen sind dieselben wie im EPUB-Leser.
 */
import { readerFarbThemen } from "../constants/themes.js";

const SCHLUESSEL = "textansicht";
const SCHRIFT_MIN = 70;
const SCHRIFT_MAX = 220;
const SCHRIFT_SCHRITT = 10;

function lade() {
  try {
    return JSON.parse(localStorage.getItem(SCHLUESSEL) || "{}");
  } catch {
    return {};
  }
}

function erzeuge() {
  const gemerkt = lade();
  let an = $state(gemerkt.an === true);
  let schrift = $state(Number(gemerkt.schrift) || 100);
  let themaIndex = $state(Math.min(Number(gemerkt.thema) || 0, readerFarbThemen.length - 1));

  function merke() {
    try {
      localStorage.setItem(SCHLUESSEL, JSON.stringify({ an, schrift, thema: themaIndex }));
    } catch { /* Speicher voll oder gesperrt */ }
  }

  return {
    get an() { return an; },
    get schrift() { return schrift; },
    get thema() { return readerFarbThemen[themaIndex]; },
    get kannKleiner() { return schrift > SCHRIFT_MIN; },
    get kannGroesser() { return schrift < SCHRIFT_MAX; },
    umschalten() { an = !an; merke(); },
    kleiner() { schrift = Math.max(SCHRIFT_MIN, schrift - SCHRIFT_SCHRITT); merke(); },
    groesser() { schrift = Math.min(SCHRIFT_MAX, schrift + SCHRIFT_SCHRITT); merke(); },
    naechstesThema() { themaIndex = (themaIndex + 1) % readerFarbThemen.length; merke(); },
  };
}

export const textansicht = erzeuge();
