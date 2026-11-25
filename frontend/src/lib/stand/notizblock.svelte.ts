// Schnellnotiz: ein Text für diesen Browser, sofort gemerkt. Andere Stellen hängen an oder ersetzen.
import { lies, merke, vergiss } from "../speicher";

const TEXT = "bf-schnellnotiz";


class Notizblock {
  #text = $state(lies(TEXT));

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
}

export const notizblock = new Notizblock();
