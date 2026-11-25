// Blättern oder Scrollen, je Gerät gemerkt. Bücher mit eigenem Umbruch (EPUB, MOBI) blättern von Haus aus, Blätter (PDF, MD,
// TXT) scrollen; gemerkt wird getrennt, damit ein Versuch beim einen nicht das andere umstellt.
import { lies, merke } from "../speicher";
import type { Leseart } from "./fluss/fluss";

export const LESEARTEN: [Leseart, string, string][] = [["blaettern", "Blättern", "book-open"], ["scrollen", "Scrollen", "arrows-up-down"]];

class Leseartwahl {
  #art = $state<Leseart>("scrollen");

  constructor(private schluessel: string, vorgabe: Leseart) {
    const g = lies(schluessel);
    this.#art = g === "blaettern" || g === "scrollen" ? g : vorgabe;
  }

  get art(): Leseart {
    return this.#art;
  }

  setze(art: Leseart): void {
    this.#art = art;
    merke(this.schluessel, art);
  }
}

export const leseart = { blatt: new Leseartwahl("leser.art.blatt", "scrollen"), buch: new Leseartwahl("leser.art.buch", "blaettern") };
