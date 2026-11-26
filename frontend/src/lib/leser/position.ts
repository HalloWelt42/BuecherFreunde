// Merkt die Lesestelle: nach kurzer Ruhe, beim Verlassen und beim Schließen der Seite sofort
import { anfrage } from "../api/client";
import type { Lesewerte } from "../lesestand";
import { buecher } from "../stand/buecher.svelte";
import { wahl } from "../stand/wahl.svelte";

const RUHE_MS = 1500;

/** Wohin eine Lesestelle gehört: der Lesestand eines Buchs (des Originals) oder der einer Übersetzung (BF-71) */
export interface Lesestandsort {
  /** Adresse des Lesers; nur dort wird die Stelle in der Adresse nachgeführt */
  pfad: string;
  /** An den Server, auch noch beim Verlassen der Seite */
  sende(position: string): Promise<unknown>;
  /** Sofort in den Listen der Oberfläche */
  uebernimm(position: string): void;
}

/** Der Lesestand des Buchs: gilt in Bibliothek, Weiterlesen und Vorschau */
export function buchort(buch: number): Lesestandsort {
  return {
    pfad: `/book/${buch}/read`,
    // keepalive: der Browser schickt auch dann zu Ende, wenn die Seite gerade verlassen wird
    sende: (position) => anfrage(`/api/books/${buch}/leseposition`, { method: "PATCH", body: JSON.stringify({ position }), keepalive: true }),
    uebernimm: (position) => {
      const neu = { reading_position: position, last_read_at: new Date().toISOString() };
      buecher.aktualisiere(buch, neu);
      wahl.aktualisiere(buch, neu);
    },
  };
}

export class Positionsspeicher {
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #offen: string | null = null;

  constructor(private ort: Lesestandsort, private art: "pdf" | "epub" | "txt") {}

  /** Stelle und Darstellung vormerken und die Adresse nachführen */
  merke(werte: Lesewerte, adresse: Record<string, string | number | undefined> = {}): void {
    this.#offen = `${this.art}:${JSON.stringify(werte)}`;
    this.#fuehreAdresseNach(adresse);
    clearTimeout(this.#uhr);
    this.#uhr = setTimeout(() => this.sofort(), RUHE_MS);
  }

  #fuehreAdresseNach(adresse: Record<string, string | number | undefined>): void {
    const pfad = this.ort.pfad;
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
    this.ort.uebernimm(position);
    this.ort.sende(position).catch(() => {
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
