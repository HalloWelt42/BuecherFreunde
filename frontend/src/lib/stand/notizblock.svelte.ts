// Schnellnotiz: ein Text für diesen Browser, sofort gemerkt. Andere Stellen hängen an oder ersetzen.
import { lies, liesJson, merke, merkeJson, vergiss } from "../speicher";

const TEXT = "bf-schnellnotiz";
const ORT = "bf-schnellnotiz-pos";

export interface Notizort {
  x: number;
  y: number;
  w: number;
  h: number;
}

class Notizblock {
  #text = $state(lies(TEXT));
  ort = $state<Notizort | null>(liesJson<Notizort | null>(ORT, null));

  woerter = $derived(this.#text.trim() ? this.#text.trim().split(/\s+/).length : 0);

  get text(): string {
    return this.#text;
  }
  set text(wert: string) {
    this.#text = wert;
    if (wert) merke(TEXT, wert);
    else vergiss(TEXT);
  }

  haengeAn(zusatz: string): void {
    this.text = this.#text.trim() ? `${this.#text.trimEnd()}\n\n${zusatz}` : zusatz;
  }

  merkeOrt(ort: Notizort): void {
    this.ort = ort;
    merkeJson(ORT, ort);
  }
}

export const notizblock = new Notizblock();
