// Marken am Rand an oder aus, je Gerät gemerkt
import { lies, merke } from "../speicher";

const SCHLUESSEL = "leser.marken";

class Randschalter {
  #an = $state(lies(SCHLUESSEL) !== "aus");
  get an(): boolean {
    return this.#an;
  }
  set an(wert: boolean) {
    this.#an = wert;
    merke(SCHLUESSEL, wert ? "an" : "aus");
  }
}

export const randmarken = new Randschalter();
