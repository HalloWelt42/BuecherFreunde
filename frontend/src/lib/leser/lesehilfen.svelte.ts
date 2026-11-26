// Lesehilfen am Rechner, je Gerät gemerkt: Fokus (Fenster, Lineal, Absatz), Ruhe, von selbst lesen, das Blatt (Helligkeit,
// Kontrast, Wärme, Graustufen, Abbildungen) und der Satz (Zeichen-, Wort-, Absatzabstand, Ausrichtung, Silbentrennung). Dazu
// Voreinstellungen, mitgeliefert und eigene, auf Wunsch je Buch gemerkt.
import { liesJson, merkeJson } from "../speicher";
import { schale } from "../stand/schale.svelte";
import { FARBTHEMEN, type Bereich } from "./darstellung";

export type Fokusart = "fenster" | "lineal" | "absatz";
export type Huelle = "dunkel" | "milchig";

export interface Fokus {
  an: boolean;
  art: Fokusart;
  huelle: Huelle;
  /** Deckkraft außen, 0 bis 1 */
  staerke: number;
  /** Weicher Übergang in Pixeln */
  verlauf: number;
  farbe: string;
  /** Fenster als Anteil der Fläche: Mitte x, Mitte y, Breite, Höhe */
  fenster: { x: number; y: number; b: number; h: number };
  zeilen: number;
  /** Lineal folgt der Maus; sonst steht es fest am Schirm, auf dieser Höhe (Anteil der Fläche, Mitte des Bands) */
  folgt: boolean;
  linie: number;
}

export interface Blatthilfen {
  helligkeit: number;
  kontrast: number;
  waerme: number;
  grau: number;
  /** Helligkeit der Abbildungen, 100 heißt unverändert */
  bilder: number;
  /** in Hundertstel em */
  zeichen: number;
  woerter: number;
  /** Abstand nach einem Absatz in Zehntel em */
  absatz: number;
  ausrichtung: "links" | "block";
  trennung: boolean;
}

export interface Voreinstellung {
  name: string;
  fg: string;
  bg: string;
  hilfen: Blatthilfen;
  /** Mitgeliefert, nicht umzubenennen und nicht zu löschen */
  fest?: boolean;
}

export const BEREICHE: Record<"helligkeit" | "kontrast" | "waerme" | "grau" | "bilder" | "zeichen" | "woerter" | "absatz" | "verlauf" | "staerke" | "zeilen" | "tempo", Bereich> = {
  helligkeit: { min: 60, max: 130, schritt: 5, vorgabe: 100 },
  kontrast: { min: 70, max: 140, schritt: 5, vorgabe: 100 },
  waerme: { min: 0, max: 60, schritt: 5, vorgabe: 0 },
  grau: { min: 0, max: 100, schritt: 10, vorgabe: 0 },
  bilder: { min: 40, max: 100, schritt: 5, vorgabe: 100 },
  zeichen: { min: 0, max: 15, schritt: 1, vorgabe: 0 },
  woerter: { min: 0, max: 40, schritt: 2, vorgabe: 0 },
  absatz: { min: 0, max: 30, schritt: 1, vorgabe: 9 },
  verlauf: { min: 0, max: 160, schritt: 8, vorgabe: 48 },
  staerke: { min: 20, max: 95, schritt: 5, vorgabe: 75 },
  zeilen: { min: 1, max: 8, schritt: 1, vorgabe: 3 },
  /** Zeilen je Minute beim Lesen von selbst */
  tempo: { min: 4, max: 80, schritt: 2, vorgabe: 18 },
};

export const OHNE: Blatthilfen = { helligkeit: 100, kontrast: 100, waerme: 0, grau: 0, bilder: 100, zeichen: 0, woerter: 0, absatz: 9, ausrichtung: "links", trennung: true };

const [hell, sepia, daemmerung, , nacht] = FARBTHEMEN;
export const MITGELIEFERT: Voreinstellung[] = [
  { name: "Tag", fg: hell.fg, bg: hell.bg, hilfen: OHNE, fest: true },
  { name: "Papier", fg: sepia.fg, bg: sepia.bg, hilfen: { ...OHNE, waerme: 15 }, fest: true },
  { name: "Abend", fg: daemmerung.fg, bg: daemmerung.bg, hilfen: { ...OHNE, helligkeit: 90, waerme: 25, bilder: 85 }, fest: true },
  { name: "Nacht", fg: nacht.fg, bg: nacht.bg, hilfen: { ...OHNE, helligkeit: 85, kontrast: 95, bilder: 70 }, fest: true },
];

const FOKUS: Fokus = { an: false, art: "lineal", huelle: "dunkel", staerke: 0.75, verlauf: 48, farbe: "#000000", fenster: { x: 0.5, y: 0.45, b: 0.6, h: 0.5 }, zeilen: 3, folgt: true, linie: 0.4 };
export const FOKUSFARBEN: [string, string][] = [["#000000", "Schwarz"], ["#1d2a28", "Nachtgrün"], ["#3d2b1f", "Braun"], ["#ffffff", "Weiß"]];

interface Gemerkt {
  fokus: Fokus;
  hilfen: Blatthilfen;
  ruhe: boolean;
  tempo: number;
  eigene: Voreinstellung[];
  /** Buch und Name der Voreinstellung, die für dieses Buch gilt */
  jeBuch: Record<string, string>;
}

const SCHLUESSEL = "leser.hilfen";

class Lesehilfen {
  #w = $state<Gemerkt>({ fokus: FOKUS, hilfen: OHNE, ruhe: false, tempo: BEREICHE.tempo.vorgabe, eigene: [], jeBuch: {} });

  constructor() {
    const g = liesJson<Partial<Gemerkt>>(SCHLUESSEL, {});
    this.#w = {
      fokus: { ...FOKUS, ...g.fokus, fenster: { ...FOKUS.fenster, ...g.fokus?.fenster }, an: false },
      hilfen: { ...OHNE, ...g.hilfen },
      ruhe: g.ruhe === true,
      tempo: g.tempo ?? BEREICHE.tempo.vorgabe,
      eigene: Array.isArray(g.eigene) ? g.eigene : [],
      jeBuch: g.jeBuch ?? {},
    };
  }

  #merke(): void {
    merkeJson(SCHLUESSEL, this.#w);
  }

  get fokus(): Fokus {
    return this.#w.fokus;
  }
  setzeFokus(neu: Partial<Fokus>): void {
    this.#w.fokus = { ...this.#w.fokus, ...neu };
    this.#merke();
  }
  get hilfen(): Blatthilfen {
    return this.#w.hilfen;
  }
  /** Was auf dem Blatt wirkt: am Telefon gibt es die Hilfen nicht, auch nicht gemerkte (BF-40) */
  get wirksam(): Blatthilfen {
    return schale.telefon ? OHNE : this.#w.hilfen;
  }
  setzeHilfen(neu: Partial<Blatthilfen>): void {
    this.#w.hilfen = { ...this.#w.hilfen, ...neu };
    this.#merke();
  }
  get ruhe(): boolean {
    return this.#w.ruhe;
  }
  set ruhe(an: boolean) {
    this.#w.ruhe = an;
    this.#merke();
  }
  get tempo(): number {
    return this.#w.tempo;
  }
  set tempo(wert: number) {
    this.#w.tempo = wert;
    this.#merke();
  }

  get voreinstellungen(): Voreinstellung[] {
    return [...MITGELIEFERT, ...this.#w.eigene];
  }
  /** Speichert, was gerade gilt, unter einem Namen; ein gleichnamiger eigener wird ersetzt */
  speichere(name: string, fg: string, bg: string): Voreinstellung | null {
    const n = name.trim().slice(0, 40);
    if (!n || MITGELIEFERT.some((v) => v.name === n)) return null;
    const v: Voreinstellung = { name: n, fg, bg, hilfen: { ...this.#w.hilfen } };
    this.#w.eigene = [...this.#w.eigene.filter((x) => x.name !== n), v];
    this.#merke();
    return v;
  }
  benenne(alt: string, neu: string): boolean {
    const n = neu.trim().slice(0, 40);
    if (!n || this.voreinstellungen.some((v) => v.name === n)) return false;
    this.#w.eigene = this.#w.eigene.map((v) => (v.name === alt ? { ...v, name: n } : v));
    this.#w.jeBuch = Object.fromEntries(Object.entries(this.#w.jeBuch).map(([b, x]) => [b, x === alt ? n : x]));
    this.#merke();
    return true;
  }
  loesche(name: string): void {
    this.#w.eigene = this.#w.eigene.filter((v) => v.name !== name);
    this.#w.jeBuch = Object.fromEntries(Object.entries(this.#w.jeBuch).filter(([, x]) => x !== name));
    this.#merke();
  }
  /** Wie viele Bücher sich diese Voreinstellung gemerkt haben */
  buecherMit(name: string): number {
    return Object.values(this.#w.jeBuch).filter((x) => x === name).length;
  }
  fuerBuch(buch: number): Voreinstellung | undefined {
    const name = this.#w.jeBuch[String(buch)];
    return name ? this.voreinstellungen.find((v) => v.name === name) : undefined;
  }
  merkeFuerBuch(buch: number, name: string | null): void {
    const neu = { ...this.#w.jeBuch };
    if (name) neu[String(buch)] = name;
    else delete neu[String(buch)];
    this.#w.jeBuch = neu;
    this.#merke();
  }
}

export const lesehilfen = new Lesehilfen();

/** CSS-Werte für das Blatt; Filter wirken auf die ganze Fläche, Abstände nur auf Text */
export function hilfenCss(h: Blatthilfen): Record<string, string> {
  const filter = [
    h.helligkeit !== 100 && `brightness(${h.helligkeit / 100})`, h.kontrast !== 100 && `contrast(${h.kontrast / 100})`,
    h.waerme && `sepia(${h.waerme / 100})`, h.grau && `grayscale(${h.grau / 100})`,
  ].filter(Boolean).join(" ");
  return {
    "--hilfe-filter": filter || "none",
    "--hilfe-bilder": h.bilder === 100 ? "none" : `brightness(${h.bilder / 100})`,
    "--hilfe-zeichen": h.zeichen ? `${h.zeichen / 100}em` : "normal",
    "--hilfe-woerter": h.woerter ? `${h.woerter / 100}em` : "normal",
    "--hilfe-absatz": `${h.absatz / 10}em`,
    "--hilfe-ausrichtung": h.ausrichtung === "block" ? "justify" : "start",
    "--hilfe-trennung": h.trennung ? "auto" : "manual",
  };
}

/** Dasselbe als Regeln für einen Kapitelrahmen (EPUB); dort gegen die Stile des Buchs */
export function hilfenEpubCss(h: Blatthilfen): string {
  const v = hilfenCss(h);
  const regeln: string[] = [];
  if (h.bilder !== 100) regeln.push(`img, svg, video { filter: ${v["--hilfe-bilder"]} !important; }`);
  if (h.zeichen || h.woerter) regeln.push(`body, body *:not(pre):not(code):not(pre *) { letter-spacing: ${v["--hilfe-zeichen"]} !important; word-spacing: ${v["--hilfe-woerter"]} !important; }`);
  if (h.absatz !== OHNE.absatz) regeln.push(`p { margin-bottom: ${v["--hilfe-absatz"]} !important; }`);
  if (h.ausrichtung === "block") regeln.push("p, li { text-align: justify !important; }");
  if (!h.trennung) regeln.push("p, li, blockquote { hyphens: manual !important; -webkit-hyphens: manual !important; }");
  return regeln.join("\n");
}
