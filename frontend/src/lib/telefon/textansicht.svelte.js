/**
 * Einstellungen der Textansicht eines PDF, je Gerät gemerkt: ob sie an ist, Schriftgröße (feine Stufen über einen
 * weiten Bereich), Schriftart, Zeilenabstand und Farbthema. Die Farbthemen sind dieselben wie im EPUB-Leser.
 */
import { readerFarbThemen } from "../constants/themes.js";

const SCHLUESSEL = "textansicht";

export const SCHRIFTGROESSE = { min: 60, max: 300, schritt: 5, vorgabe: 110 };
export const ZEILENABSTAND = { min: 1.2, max: 2.4, schritt: 0.1, vorgabe: 1.6 };

// Schriftnamen sind technische Bezeichner der gebündelten Schriften
export const SCHRIFTARTEN = [
  { kennung: "literata", name: "Literata", familie: '"Literata", Georgia, serif' },
  { kennung: "atkinson", name: "Atkinson Hyperlegible", familie: '"Atkinson Hyperlegible", system-ui, sans-serif' },
  { kennung: "georgia", name: "Georgia", familie: 'Georgia, "Times New Roman", serif' },
  { kennung: "barlow", name: "Barlow", familie: "Barlow, system-ui, sans-serif" },
  { kennung: "system", name: "System", familie: "system-ui, -apple-system, sans-serif" },
];

function lade() {
  try {
    return JSON.parse(localStorage.getItem(SCHLUESSEL) || "{}");
  } catch {
    return {};
  }
}

function begrenzt(wert, { min, max, vorgabe }) {
  const zahl = Number(wert);
  return Number.isFinite(zahl) && zahl >= min && zahl <= max ? zahl : vorgabe;
}

function erzeuge() {
  const gemerkt = lade();
  let an = $state(gemerkt.an === true);
  let groesse = $state(begrenzt(gemerkt.groesse, SCHRIFTGROESSE));
  let zeilenabstand = $state(begrenzt(gemerkt.zeilenabstand, ZEILENABSTAND));
  let schriftart = $state(SCHRIFTARTEN.some((s) => s.kennung === gemerkt.schriftart) ? gemerkt.schriftart : "literata");
  let themaIndex = $state(begrenzt(gemerkt.thema, { min: 0, max: readerFarbThemen.length - 1, vorgabe: 0 }));

  function merke() {
    try {
      localStorage.setItem(SCHLUESSEL, JSON.stringify({ an, groesse, zeilenabstand, schriftart, thema: themaIndex }));
    } catch { /* Speicher voll oder gesperrt */ }
  }

  function setzeGroesse(wert) {
    groesse = Math.min(SCHRIFTGROESSE.max, Math.max(SCHRIFTGROESSE.min, Math.round(wert)));
    merke();
  }

  function setzeZeilenabstand(wert) {
    zeilenabstand = Math.round(Math.min(ZEILENABSTAND.max, Math.max(ZEILENABSTAND.min, wert)) * 10) / 10;
    merke();
  }

  return {
    get an() { return an; },
    get groesse() { return groesse; },
    get zeilenabstand() { return zeilenabstand; },
    get schriftart() { return schriftart; },
    get familie() { return SCHRIFTARTEN.find((s) => s.kennung === schriftart).familie; },
    get themaIndex() { return themaIndex; },
    get thema() { return readerFarbThemen[themaIndex]; },
    umschalten() { an = !an; merke(); },
    setzeGroesse,
    kleiner() { setzeGroesse(groesse - SCHRIFTGROESSE.schritt); },
    groesser() { setzeGroesse(groesse + SCHRIFTGROESSE.schritt); },
    setzeZeilenabstand,
    setzeSchriftart(kennung) { schriftart = kennung; merke(); },
    setzeThema(index) { themaIndex = index; merke(); },
  };
}

export const textansicht = erzeuge();
