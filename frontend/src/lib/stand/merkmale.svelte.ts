// Favorit, Lesesofa, Gelesen, Sterne: eine Stelle ändert am Server und zieht Liste, Vorschau und Zahlen nach
import { setzeBewertung, toggleFavorit, toggleGelesen, toggleZumLesen } from "../api/user-data";
import type { Buch } from "../typen";
import { bestand } from "./bestand.svelte";
import { buecher } from "./buecher.svelte";
import { melde } from "./meldungen.svelte";
import { wahl } from "./wahl.svelte";

type Merkbar = Pick<Buch, "id" | "is_favorite" | "is_to_read" | "last_read_at" | "rating">;

function verteile(id: number, neu: Partial<Buch>): void {
  buecher.aktualisiere(id, neu);
  wahl.aktualisiere(id, neu);
}

async function aendere(buch: Merkbar, tun: () => Promise<Partial<Buch>>): Promise<Partial<Buch>> {
  try {
    const neu = await tun();
    verteile(buch.id, neu);
    void bestand.laden();
    return neu;
  } catch (e) {
    melde.schlecht(e, "Nicht gespeichert");
    return {};
  }
}

export const merkmale = {
  favorit: (buch: Merkbar) =>
    aendere(buch, async () => {
      const a = await toggleFavorit(buch.id);
      return { is_favorite: a.ist_favorit ?? !buch.is_favorite };
    }),
  sofa: (buch: Merkbar) =>
    aendere(buch, async () => {
      const a = await toggleZumLesen(buch.id);
      return { is_to_read: a.zu_lesen ?? !buch.is_to_read };
    }),
  gelesen: (buch: Merkbar) =>
    aendere(buch, async () => {
      const a = await toggleGelesen(buch.id);
      return { last_read_at: (a.gelesen ?? !buch.last_read_at) ? new Date().toISOString() : null };
    }),
  sterne: (buch: Merkbar, wert: number) =>
    aendere(buch, async () => {
      const a = await setzeBewertung(buch.id, wert);
      return { rating: a.bewertung ?? wert };
    }),
};
