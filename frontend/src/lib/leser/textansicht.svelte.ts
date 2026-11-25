// Textansicht eines PDF, je Gerät gemerkt: ob sie am Telefon an ist, Größe, Schrift, Zeilenabstand, Farbthema
import { liesJson, merkeJson } from "../speicher";
import { FARBTHEMEN, GROESSE, klemme, oderVorgabe, ZEILEN, type Farbthema } from "./darstellung";

const SCHLUESSEL = "textansicht";

/** Kennungen, unter denen die Schriften gemerkt sind */
const SCHRIFTEN: [string, string][] = [
  ["literata", '"Literata", Georgia, serif'], ["atkinson", '"Atkinson Hyperlegible", system-ui, sans-serif'], ["barlow", "Barlow, sans-serif"],
  ["jetbrains", "'JetBrains Mono', monospace"], ["georgia", "Georgia, 'Times New Roman', serif"], ["system", "system-ui, -apple-system, sans-serif"],
];

interface Gemerkt {
  an?: boolean;
  groesse?: number;
  zeilenabstand?: number;
  schriftart?: string;
  thema?: number;
}

class Textansicht {
  #w = $state<Required<Gemerkt>>({ an: false, groesse: 110, zeilenabstand: ZEILEN.vorgabe, schriftart: "literata", thema: -1 });

  constructor() {
    const g = liesJson<Gemerkt>(SCHLUESSEL, {});
    this.#w = {
      an: g.an === true,
      groesse: g.groesse ? oderVorgabe(g.groesse, GROESSE) : 110,
      zeilenabstand: oderVorgabe(g.zeilenabstand, ZEILEN),
      schriftart: SCHRIFTEN.some(([k]) => k === g.schriftart) ? g.schriftart! : "literata",
      thema: typeof g.thema === "number" && FARBTHEMEN[g.thema] ? g.thema : -1,
    };
  }

  #setze(neu: Gemerkt): void {
    this.#w = { ...this.#w, ...neu };
    merkeJson(SCHLUESSEL, { ...this.#w, thema: this.#w.thema < 0 ? undefined : this.#w.thema });
  }

  get an(): boolean {
    return this.#w.an;
  }
  set an(wert: boolean) {
    this.#setze({ an: wert });
  }
  get groesse(): number {
    return this.#w.groesse;
  }
  set groesse(wert: number) {
    this.#setze({ groesse: klemme(wert, GROESSE) });
  }
  get zeilen(): number {
    return this.#w.zeilenabstand;
  }
  set zeilen(wert: number) {
    this.#setze({ zeilenabstand: klemme(wert, ZEILEN) });
  }
  get familie(): string {
    return SCHRIFTEN.find(([k]) => k === this.#w.schriftart)![1];
  }
  set familie(wert: string) {
    const gleich = SCHRIFTEN.find(([, f]) => f.split(",")[0].replace(/["']/g, "") === wert.split(",")[0].replace(/["']/g, ""));
    if (gleich) this.#setze({ schriftart: gleich[0] });
  }
  /** -1: noch nie gewählt, dann folgt sie der App */
  get themaNr(): number {
    return this.#w.thema;
  }
  thema(vorgabe: Farbthema): Farbthema {
    return FARBTHEMEN[this.#w.thema] ?? vorgabe;
  }
  setzeThema(nr: number): void {
    this.#setze({ thema: nr });
  }
}

export const textansicht = new Textansicht();
