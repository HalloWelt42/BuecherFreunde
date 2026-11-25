// Filter der Bibliothek. Die Wahrheit steht in der Adresse; gemerkt wird sie für den nächsten Start der App.
import { navigate, route } from "../router.svelte.js";
import { lies, merke } from "../speicher";

const SCHLUESSEL = "lib_filter";
/** Mehrere Werte zugleich, mit Komma getrennt */
const MEHRERE = ["category", "file_format"];
const BEKANNT = ["category", "sammlung", "file_format", "min_rating", "is_favorite", "is_to_read", "gelesen", "hat_isbn", "hat_highlights", "weiterlesen", "hat_labels"];

class Filter {
  #werte = $derived.by(() => {
    const aus = new Map<string, string>();
    if (route.path !== "/") return aus;
    const p = new URLSearchParams(route.qs || "");
    for (const k of BEKANNT) {
      const w = p.get(k);
      if (w) aus.set(k, w);
    }
    return aus;
  });

  aktiv = $derived(this.#werte.size > 0);
  /** Adressteil ohne Fragezeichen, stabil sortiert: ändert er sich, lädt die Liste neu */
  kennung = $derived([...this.#werte].map(([k, w]) => `${k}=${w}`).join("&"));

  wert(schluessel: string): string {
    return this.#werte.get(schluessel) ?? "";
  }

  werte(schluessel: string): string[] {
    const w = this.wert(schluessel);
    return w ? w.split(",") : [];
  }

  hat(schluessel: string, wert: string): boolean {
    return this.werte(schluessel).includes(wert);
  }

  schalte(schluessel: string, wert: string): void {
    if (!MEHRERE.includes(schluessel)) {
      this.setze(schluessel, this.hat(schluessel, wert) ? "" : wert);
      return;
    }
    const jetzt = this.werte(schluessel);
    this.setze(schluessel, (jetzt.includes(wert) ? jetzt.filter((w) => w !== wert) : [...jetzt, wert]).join(","));
  }

  setze(schluessel: string, wert: string): void {
    const p = new URLSearchParams([...this.#werte]);
    if (wert) p.set(schluessel, wert);
    else p.delete(schluessel);
    this.#gehe(p.toString());
  }

  leere(): void {
    this.#gehe("");
  }

  #gehe(qs: string): void {
    merke(SCHLUESSEL, qs);
    navigate(qs ? `/?${qs}` : "/");
  }

  /** Nur beim ersten Öffnen der App an der nackten Adresse: dort weiter, wo man aufgehört hat */
  stelleWiederHer(): void {
    const gemerkt = lies(SCHLUESSEL);
    if (gemerkt && route.path === "/" && !route.qs) navigate(`/?${gemerkt}`, true);
  }
}

export const filter = new Filter();
