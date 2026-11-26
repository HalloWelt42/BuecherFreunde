// Ein Textbuch (TXT, MD) im Kinderleser: Absätze, Überschriften aus Markdown, Einheiten zu je einigen Absätzen; eine neue
// Einheit beginnt an jeder Überschrift. Der Lesestand ist ein Anteil, wie beim normalen Leser für Texte.
import { anfrage } from "../api/client";
import type { Lesewerte } from "../lesestand";
import { einheitAus, type Kinderquelle, type Textstueck } from "./inhalt";
import type { Einheit, Kinderstelle } from "./typen";

const STUECK = 2400;

/** Absätze und Überschriften; Markdown nur so weit, wie es für Kinderbücher nötig ist */
export function textstueckeAus(text: string, markdown: boolean): Textstueck[] {
  const aus: Textstueck[] = [];
  for (const roh of text.replace(/\r\n?/g, "\n").split(/\n\s*\n/)) {
    const absatz = roh.trim();
    if (!absatz) continue;
    const titel = markdown ? /^#{1,6}\s+(.*)$/s.exec(absatz) : null;
    const rein = (titel ? titel[1] : absatz).replace(/\s+/g, " ");
    aus.push({ art: titel ? "titel" : "absatz", text: markdown ? rein.replace(/[*_`]+/g, "").replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1") : rein });
  }
  return aus;
}

/** Stücke zu Einheiten: höchstens etwa STUECK Zeichen, neu an jeder Überschrift */
export function einheitenAus(stuecke: Textstueck[]): Textstueck[][] {
  const aus: Textstueck[][] = [];
  let laenge = 0;
  for (const s of stuecke) {
    if (!aus.length || s.art === "titel" || laenge + s.text.length > STUECK) {
      aus.push([]);
      laenge = 0;
    }
    aus[aus.length - 1].push(s);
    laenge += s.text.length;
  }
  return aus.length ? aus : [[]];
}

export class Textkinderquelle implements Kinderquelle {
  readonly art = "txt";
  #einheiten: Einheit[];

  private constructor(gruppen: Textstueck[][]) {
    this.#einheiten = gruppen.map((g, nr) => einheitAus(nr, g));
  }

  static async oeffne(adresse: string, markdown: boolean): Promise<Textkinderquelle> {
    const text = await (await anfrage(adresse)).text();
    return new Textkinderquelle(einheitenAus(textstueckeAus(text, markdown)));
  }

  get anzahl(): number {
    return this.#einheiten.length;
  }

  name(einheit: number): string {
    return `Stück ${einheit + 1}`;
  }

  async einheit(nr: number): Promise<Einheit> {
    return this.#einheiten[nr] ?? einheitAus(nr, []);
  }

  #anteil(stelle: Kinderstelle): number {
    const laenge = this.#einheiten[stelle.einheit]?.text.length || 1;
    return (stelle.einheit + Math.min(1, stelle.zeichen / laenge)) / Math.max(1, this.anzahl);
  }

  async lesewerte(stelle: Kinderstelle): Promise<Lesewerte> {
    return { scrollPct: Math.round(this.#anteil(stelle) * 1000) / 10 };
  }

  async stelleAus(werte: Lesewerte): Promise<Kinderstelle | null> {
    const pct = werte.scrollPct ?? werte.percent;
    return typeof pct === "number" ? { einheit: Math.min(this.anzahl - 1, Math.floor((pct / 100) * this.anzahl)), zeichen: 0 } : null;
  }

  async markierungsort(einheit: number, von: number): Promise<string> {
    return `percent:${Math.round(this.#anteil({ einheit, zeichen: von }) * 1000) / 10}`;
  }

  async einheitDer(ort: string): Promise<number | null> {
    const pct = Number(/^percent:([\d.]+)/.exec(ort)?.[1]);
    return Number.isFinite(pct) ? Math.min(this.anzahl - 1, Math.floor((pct / 100) * this.anzahl)) : null;
  }

  ort(stelle: Kinderstelle): string {
    return `${Math.round(this.#anteil(stelle) * 100)}%`;
  }

  schliesse(): void {}
}
