// Merkt die Lesestelle: nach kurzer Ruhe, beim Verlassen und beim Schließen der Seite sofort
import { anfrage } from "../api/client";
import type { Lesewerte } from "../lesestand";
import { buecher } from "../stand/buecher.svelte";
import { wahl } from "../stand/wahl.svelte";

const RUHE_MS = 1500;

export class Positionsspeicher {
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #offen: string | null = null;

  constructor(private buch: number, private art: "pdf" | "epub" | "txt") {}

  /** Stelle und Darstellung vormerken und die Adresse nachführen */
  merke(werte: Lesewerte, adresse: Record<string, string | number | undefined> = {}): void {
    this.#offen = `${this.art}:${JSON.stringify(werte)}`;
    this.#fuehreAdresseNach(adresse);
    clearTimeout(this.#uhr);
    this.#uhr = setTimeout(() => this.sofort(), RUHE_MS);
  }

  #fuehreAdresseNach(adresse: Record<string, string | number | undefined>): void {
    const pfad = `/book/${this.buch}/read`;
    if (location.pathname !== pfad) return;
    const p = new URLSearchParams();
    for (const [k, w] of Object.entries(adresse)) if (w !== undefined && w !== "") p.set(k, String(w));
    const q = p.toString();
    history.replaceState(history.state, "", q ? `${pfad}?${q}` : pfad);
  }

  sofort(): void {
    clearTimeout(this.#uhr);
    const position = this.#offen;
    if (position === null) return;
    this.#offen = null;
    const neu = { reading_position: position, last_read_at: new Date().toISOString() };
    buecher.aktualisiere(this.buch, neu);
    wahl.aktualisiere(this.buch, neu);
    // keepalive: der Browser schickt auch dann zu Ende, wenn die Seite gerade verlassen wird
    anfrage(`/api/books/${this.buch}/leseposition`, { method: "PATCH", body: JSON.stringify({ position }), keepalive: true }).catch(() => {
      // Nicht angekommen und nichts Neueres da: beim nächsten Anlass noch einmal
      this.#offen ??= position;
    });
  }

  /** Ab jetzt auch beim Verlassen speichern; liefert das Aufräumen */
  starte(): () => void {
    const jetzt = () => this.sofort();
    const verdeckt = () => document.visibilityState === "hidden" && this.sofort();
    addEventListener("pagehide", jetzt);
    document.addEventListener("visibilitychange", verdeckt);
    return () => {
      removeEventListener("pagehide", jetzt);
      document.removeEventListener("visibilitychange", verdeckt);
      this.sofort();
    };
  }
}
