// Innerer Rand des Blatts in allen Texten, je Gerät gemerkt
import { geraet } from "../stand/geraet.svelte";
import { lies, merke } from "../speicher";
import { klemme, type Bereich } from "./darstellung";

const SCHLUESSEL = "leser.rand";
/** So viel bleibt im Vollbild oben frei, damit das Zeichen zum Verlassen nie auf einer Zeile liegt */
const ZEICHEN_FREI = 28;

class Blattrand {
  readonly bereich: Bereich = { min: 0, max: 120, schritt: 4, vorgabe: geraet.telefon ? 20 : 52 };
  #wert = $state(this.bereich.vorgabe);

  constructor() {
    const g = lies(SCHLUESSEL);
    if (g) this.#wert = klemme(Number(g) || 0, this.bereich);
  }

  get wert(): number {
    return this.#wert;
  }
  set wert(neu: number) {
    this.#wert = klemme(neu, this.bereich);
    merke(SCHLUESSEL, String(this.#wert));
  }

  /** Rand oben */
  oben(vollbild: boolean): number {
    return vollbild ? Math.max(ZEICHEN_FREI, this.#wert) : this.#wert;
  }
}

export const blattrand = new Blattrand();
