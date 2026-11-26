// Aufteilung des Leseraums am Rechner und Tablet (BF-35, BF-36, BF-41): die Bühne ist Blatt, Rand für die Marken und
// Feld. Hier steht an einer Stelle, wie viel Platz rechts bleibt und wie breit das Blatt höchstens wird; die Ansichten
// lesen es als Marken am Leser (--raum-rechts, --lesebreite) und rechnen beim Einpassen damit. Am Telefon und im
// Vollbild bleibt alles, wie es ist: das Feld schwebt über dem Buch, die Marken sind schmale Streifen am Rand.
import { lies, merke } from "../speicher";
import { klemme, type Bereich } from "./darstellung";

/** Breite einer breiten Marke am Rand; der übliche Rand der Seite bleibt rechts daneben als Luft */
export const MARKENRAND = 34;
/** Abstand des Felds rechts (Schrift und Papier, Notizen, Verzeichnis, Fokus, Tastenkürzel) zur Kante der Bühne */
const FELDFUGE = 10;
/** So schmal darf das Blatt neben dem offenen Feld höchstens werden; reicht es nicht, schwebt das Feld darüber */
const MIND_BLATT = 448;

export interface Raumlage {
  /** Breite der Bühne in Punkten */
  breite: number;
  /** Breite des offenen Felds in Punkten, wie es gezeichnet ist (folgt der Schriftstufe der App) */
  feld: number;
  /** Seitenrand der Bühne links und rechts in Punkten */
  rand: number;
  telefon: boolean;
  vollbild: boolean;
  marken: boolean;
  feldOffen: boolean;
}

export interface Aufteilung {
  /** Platz für die Marken rechts neben dem Blatt */
  markenrand: number;
  /** Das offene Feld hat seinen eigenen Platz rechts */
  feldDaneben: boolean;
  /** So viel nimmt rechts weg, wer nicht Blatt ist (Marken und Feld), zusätzlich zum Seitenrand */
  rechts: number;
}

export function teileAuf(r: Raumlage): Aufteilung {
  if (r.telefon || r.vollbild) return { markenrand: 0, feldDaneben: false, rechts: 0 };
  const markenrand = r.marken ? MARKENRAND : 0;
  const feld = r.feld + FELDFUGE;
  const feldDaneben = r.feldOffen && r.feld > 0 && r.breite - 2 * r.rand - markenrand - feld >= MIND_BLATT;
  return { markenrand, feldDaneben, rechts: markenrand + (feldDaneben ? feld : 0) };
}

const SCHLUESSEL = "leser.breite";

/** Breite des Blatts: Textspalte in Text, Markdown und EPUB, Seite im PDF beim Einpassen; je Gerät gemerkt */
class Blattbreite {
  readonly bereich: Bereich = { min: 400, max: 1600, schritt: 20, vorgabe: 720 };
  #wert = $state(this.bereich.vorgabe);

  constructor() {
    const g = lies(SCHLUESSEL);
    if (g) this.#wert = klemme(Number(g) || this.bereich.vorgabe, this.bereich);
  }

  get wert(): number {
    return this.#wert;
  }
  set wert(neu: number) {
    this.#wert = klemme(neu, this.bereich);
    merke(SCHLUESSEL, String(this.#wert));
  }
}

export const blattbreite = new Blattbreite();
