// Welche der fünf Ansichten gilt; Schlüssel und Werte wie bisher
import { lies, merke } from "../../lib/speicher";

export type Regalart = "grid" | "grid-large" | "covers" | "list" | "detail-list";

export const regalarten: [Regalart, string, string][] = [
  ["grid", "Kacheln", "grip"], ["grid-large", "Große Kacheln", "table-cells-large"], ["covers", "Nur Umschläge", "images"], ["list", "Kompakte Liste", "list"], ["detail-list", "Liste mit Einzelheiten", "table-list"],
];

const gemerkt = lies("viewMode", "grid") as Regalart;

class Regalansicht {
  #art = $state<Regalart>(regalarten.some(([a]) => a === gemerkt) ? gemerkt : "grid");

  get art(): Regalart {
    return this.#art;
  }
  set art(wert: Regalart) {
    this.#art = wert;
    merke("viewMode", wert);
  }
}

export const regalansicht = new Regalansicht();
