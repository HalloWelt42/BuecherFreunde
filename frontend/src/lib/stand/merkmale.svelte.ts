// Favorit, Lesesofa, Gelesen, Sterne, Umschlag: eine Stelle ändert am Server und zieht Liste, Vorschau und Zahlen nach
import { aktualisiereBuch, setzePrivat } from "../api/books";
import { setzeBewertung, toggleFavorit, toggleGelesen, toggleZumLesen } from "../api/user-data";
import type { Buch, Umschlagart } from "../typen";
import { bestand } from "./bestand.svelte";
import { buecher } from "./buecher.svelte";
import { melde } from "./meldungen.svelte";
import { wahl } from "./wahl.svelte";

type Merkbar = Pick<Buch, "id" | "is_favorite" | "is_to_read" | "last_read_at" | "rating" | "privat">;

function verteile(id: number, neu: Partial<Buch>): void {
  buecher.aktualisiere(id, neu);
  wahl.aktualisiere(id, neu);
}

/** Ändert, verteilt und gibt das Geänderte zurück; scheitert es, eine Meldung und nichts */
async function aendere(id: number, tun: () => Promise<Partial<Buch>>): Promise<Partial<Buch>> {
  try {
    const neu = await tun();
    verteile(id, neu);
    return neu;
  } catch (e) {
    melde.schlecht(e, "Nicht gespeichert");
    return {};
  }
}

/** Wie aendere, danach ziehen die Zahlen der Leiste nach */
async function mitZahlen(buch: Merkbar, tun: () => Promise<Partial<Buch>>): Promise<Partial<Buch>> {
  const neu = await aendere(buch.id, tun);
  if (Object.keys(neu).length) void bestand.laden();
  return neu;
}

export const merkmale = {
  favorit: (buch: Merkbar) =>
    mitZahlen(buch, async () => {
      const a = await toggleFavorit(buch.id);
      return { is_favorite: a.ist_favorit ?? !buch.is_favorite };
    }),
  sofa: (buch: Merkbar) =>
    mitZahlen(buch, async () => {
      const a = await toggleZumLesen(buch.id);
      return { is_to_read: a.zu_lesen ?? !buch.is_to_read };
    }),
  gelesen: (buch: Merkbar) =>
    mitZahlen(buch, async () => {
      const a = await toggleGelesen(buch.id);
      return { last_read_at: (a.gelesen ?? !buch.last_read_at) ? new Date().toISOString() : null };
    }),
  sterne: (buch: Merkbar, wert: number) =>
    mitZahlen(buch, async () => {
      const a = await setzeBewertung(buch.id, wert);
      return { rating: a.bewertung ?? wert };
    }),
  /** Nur für mich (BF-78): das aktive Profil behält das Buch für sich; andere Profile sehen es nicht mehr */
  privat: (buch: Merkbar) =>
    aendere(buch.id, async () => {
      const a = await setzePrivat(buch.id, !buch.privat);
      return { privat: a.privat ?? !buch.privat };
    }),
  /** Gestaltetes Blatt oder Titelseite (BF-59); was der Umschlag dann zeigt, sagt der Server */
  umschlag: (buch: Pick<Buch, "id">, art: Umschlagart) =>
    aendere(buch.id, async () => {
      const b = await aktualisiereBuch(buch.id, { umschlag_wahl: art });
      return { umschlag: b.umschlag, umschlag_wahl: b.umschlag_wahl, umschlag_schlicht: b.umschlag_schlicht };
    }),
};
