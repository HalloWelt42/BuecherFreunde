// Ein gerade gezogenes Rechteck auf einer gescannten Seite (BF-123): seine Lesung beginnt sofort und fragt nach, bis Text oder
// Grund da ist; die Auswahl daraus trägt den Text, sobald er kommt, und geht an dasselbe Menü wie eine Auswahl im Text.
import { lesestand, liesBereich, type Lesestand } from "../../api/highlights";
import { fehlertext } from "../../stand/meldungen.svelte";
import type { Textauswahl } from "../typen";
import { stelleVon, type Bereich } from "./bereich";

/** So oft fragt das Menü nach, solange gelesen wird */
export const NACHFRAGE_MS = 1500;

export interface Lesewege {
  liesBereich: (buch: number, stelle: string) => Promise<Lesestand>;
  lesestand: (lesung: number) => Promise<Lesestand>;
}

export class Lesung {
  id = $state<number | null>(null);
  stand = $state<Lesestand["stand"]>("offen");
  text = $state("");
  grund = $state("");
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #aus = false;

  constructor(buch: number, readonly stelle: string, private wege: Lesewege = { liesBereich, lesestand }) {
    void this.#beginne(buch);
  }

  async #beginne(buch: number): Promise<void> {
    try {
      this.#nimm(await this.wege.liesBereich(buch, this.stelle));
    } catch (f) {
      this.#scheitert(f);
    }
  }

  #nimm(s: Lesestand): void {
    if (this.#aus) return;
    [this.id, this.stand, this.text, this.grund] = [s.id, s.stand, s.text, s.grund];
    if (s.stand === "offen") this.#uhr = setTimeout(() => void this.#frage(), NACHFRAGE_MS);
  }

  async #frage(): Promise<void> {
    if (this.#aus || this.id === null) return;
    try {
      this.#nimm(await this.wege.lesestand(this.id));
    } catch (f) {
      this.#scheitert(f);
    }
  }

  #scheitert(f: unknown): void {
    if (this.#aus) return;
    this.stand = "fehler";
    this.grund = fehlertext(f);
  }

  /** Das Menü ist zu: nicht mehr nachfragen (eine Markierung daraus liest auf dem Server weiter) */
  beende(): void {
    this.#aus = true;
    clearTimeout(this.#uhr);
  }
}

/** Die Auswahl eines Rechtecks: wie eine Textauswahl, ihr Text ist der der Lesung (leer, solange gelesen wird) */
export class Bereichsauswahl implements Textauswahl {
  readonly cfi: string;
  constructor(readonly seite: number, readonly lage: Bereich, readonly x: number, readonly oben: number, readonly unten: number, readonly ort: string, readonly lesung: Lesung | null) {
    this.cfi = stelleVon(seite, lage);
  }

  get text(): string {
    return this.lesung?.text ?? "";
  }
}

export const istBereich = (a: Textauswahl | null): a is Bereichsauswahl => a instanceof Bereichsauswahl;
