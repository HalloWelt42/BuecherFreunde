// Nachbesserung erkannter Seiten aus der Textansicht (BF-118): um sie bitten (die Seite und die nächsten), je Seite die Fassung
// wählen, und solange gezeigte Seiten nachgebessert werden, im festen Abstand nachfragen und sie neu holen
import { texterkennungFassung, texterkennungNachbessern } from "../../api/books";
import { melde } from "../../stand/meldungen.svelte";
import type { Textseiten } from "./textseiten.svelte";

/** So oft fragt die Textansicht nach, solange eine gezeigte Seite nachgebessert wird (eine Seite dauert rund ein bis zwei Minuten) */
export const NACHFRAGE_MS = 6000;

export class Nachbesserung {
  /** Die Seite, deren Taste gerade wirkt: ihr Zeichen dreht */
  arbeit = $state<number | null>(null);
  #uhr: ReturnType<typeof setTimeout> | null = null;
  #aus = false;

  constructor(private buch: number, private text: Textseiten) {}

  async bitte(seite: number): Promise<void> {
    this.arbeit = seite;
    try {
      const a = await texterkennungNachbessern(this.buch, seite);
      if (!a.bereit) return void melde.warn(a.grund);
      await this.text.erneuere(a.seiten.length ? a.seiten : [seite]);
      this.pruefe();
    } catch (e) {
      melde.schlecht(e, "Nicht nachgebessert");
    } finally {
      this.arbeit = null;
    }
  }

  async waehle(seite: number, gilt: "klassisch" | "ki"): Promise<void> {
    this.arbeit = seite;
    try {
      await texterkennungFassung(this.buch, seite, gilt);
      await this.text.erneuere([seite]);
    } catch (e) {
      melde.schlecht(e, "Fassung nicht gewechselt");
    } finally {
      this.arbeit = null;
    }
  }

  /** Nach jeder Änderung der gezeigten Seiten: fragt bald nach, wenn eine nachgebessert wird */
  pruefe(): void {
    if (this.#aus || this.#uhr !== null || !this.text.nachbessernd.length) return;
    this.#uhr = setTimeout(() => {
      this.#uhr = null;
      const offen = this.text.nachbessernd;
      if (!this.#aus && offen.length) void this.text.erneuere(offen).then(() => this.pruefe());
    }, NACHFRAGE_MS);
  }

  halte(): void {
    this.#aus = true;
    if (this.#uhr !== null) clearTimeout(this.#uhr);
    this.#uhr = null;
  }
}
