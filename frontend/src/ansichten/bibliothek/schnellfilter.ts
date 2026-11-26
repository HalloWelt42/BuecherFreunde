// Der Schnellfilter der Bibliothek steht als q in der Adresse, bei den übrigen Filtern; der Server grenzt die Liste ein
import { buecher } from "../../lib/stand/buecher.svelte";
import { filter } from "../../lib/stand/filter.svelte";
import type { Filterziel } from "../../lib/stand/schnellfilter.svelte";

export const BUCHHINWEIS = "Titel, Autor, ISBN oder Etikett";

export const regalfilter: Filterziel = {
  get wort() {
    return filter.wert("q");
  },
  hinweis: BUCHHINWEIS,
  get treffer() {
    return buecher.geladen ? buecher.gesamt : null;
  },
  get gesamt() {
    return buecher.geladen ? buecher.ohneSuche : null;
  },
  // Wächst ein Wort beim Tippen, bleibt es ein Schritt im Verlauf; Zurück führt zur Liste ohne Filter
  filtere(wort) {
    filter.setze("q", wort, !!wort && !!filter.wert("q"));
  },
};
