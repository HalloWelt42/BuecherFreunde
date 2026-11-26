// Kontextmenü eines Buchs in Regal, Listen, Weiterlesen und Suche (BF-42): nur, was Karte und Buchseite heute schon können
import { holeBuch } from "../../lib/api/books";
import { ordneBuchZu } from "../../lib/api/categories";
import { leseAdresse, lesestand } from "../../lib/lesestand";
import { navigate } from "../../lib/router.svelte";
import { bestand } from "../../lib/stand/bestand.svelte";
import { ich } from "../../lib/stand/ich.svelte";
import type { Anbieter, Eintrag } from "../../lib/stand/kontextmenue.svelte";
import { kontextmenue } from "../../lib/stand/kontextmenue.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";
import { merkmale } from "../../lib/stand/merkmale.svelte";
import Regalwahl from "../../lib/teile/Regalwahl.svelte";
import type { Buch, Regal } from "../../lib/typen";

/** Anbieter für eine Karte; nur mit der Nummer (Treffer der Suche) wird das Buch beim Öffnen des Menüs geholt */
export function buchmenue(buch: Buch | number): Anbieter {
  return () => eintraege(buch);
}

async function stelleEin(buch: Buch, regal: Regal): Promise<void> {
  kontextmenue.schliesse();
  try {
    await ordneBuchZu(regal.id, buch.id);
    melde.gut(`In ${regal.name} gestellt`);
    bestand.geaendert();
  } catch (e) {
    melde.schlecht(e, "Nicht geändert");
  }
}

async function eintraege(b: Buch | number): Promise<Eintrag[]> {
  const buch = typeof b === "number" ? await holeBuch(b) : b;
  return [
    { text: "Öffnen", symbol: "book", tun: () => navigate(`/book/${buch.id}`) },
    { text: lesestand(buch).angefangen ? "Weiterlesen" : "Lesen", symbol: "book-open", tun: () => navigate(leseAdresse(buch.id)) },
    { text: buch.is_favorite ? "Kein Favorit mehr" : "Favorit", symbol: "heart", tun: () => merkmale.favorit(buch) },
    { text: "In ein Regal", symbol: "folder-plus", weiter: { komponente: Regalwahl, eigenschaften: { ohne: buch.categories.map((c) => c.id), onwahl: (r: Regal) => void stelleEin(buch, r) } } },
    ...(ich.darf("bearbeiten") ? [{ text: "Bearbeiten", symbol: "pen", tun: () => navigate(`/book/${buch.id}?bearbeiten`) }] : []),
  ];
}
