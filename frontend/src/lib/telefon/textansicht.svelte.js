/**
 * Einstellungen der Textansicht eines PDF, je Gerät gemerkt: ob sie an ist, Schriftgröße (feine Stufen über einen
 * weiten Bereich), Schriftart, Zeilenabstand und Farbthema. Die Farbthemen sind dieselben wie im EPUB-Leser.
 */
import { readerFarbThemen } from "../constants/themes.js";
import { SCHRIFTGROESSE, ZEILENABSTAND, SCHRIFTARTEN, klemme } from "./lesedarstellung.js";

const SCHLUESSEL = "textansicht";

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
    groesse = klemme(Math.round(wert), SCHRIFTGROESSE);
    merke();
  }

  function setzeZeilenabstand(wert) {
    zeilenabstand = Math.round(klemme(wert, ZEILENABSTAND) * 10) / 10;
    merke();
  }

  return {
    get an() { return an; },
    get groesse() { return groesse; },
    get zeilenabstand() { return zeilenabstand; },
    get schriftart() { return schriftart; },
    get familie() { return SCHRIFTARTEN.find((s) => s.kennung === schriftart).familie; },
    get themaIndex() { return themaIndex; },
    schriftarten: SCHRIFTARTEN,
    get thema() { return readerFarbThemen[themaIndex]; },
    umschalten() { an = !an; merke(); },
    setzeGroesse,
    setzeZeilenabstand,
    setzeSchriftart(kennung) { schriftart = kennung; merke(); },
    setzeThema(index) { themaIndex = index; merke(); },
  };
}

export const textansicht = erzeuge();
