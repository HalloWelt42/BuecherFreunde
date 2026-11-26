// Überschrift der Bibliothek: benennt die gesetzten Filter
import { filternamen } from "../../lib/katalog";
import { bestand } from "../../lib/stand/bestand.svelte";
import { filter } from "../../lib/stand/filter.svelte";

const NAMEN: Record<string, string> = {
  "hat_isbn=true": "Bücher", "hat_isbn=false": "Dokumente", "weiterlesen=true": "Weiterlesen", "is_favorite=true": "Favoriten", "is_to_read=true": "Lesesofa",
  "gelesen=true": "Gelesen", "gelesen=false": "Ungelesen", "hat_highlights=true": "Markiertes", "hat_labels=true": "Mit Etiketten",
  "ohne_kategorie=true": "Ohne Kategorie",
};

export function titelDerFilter(): string {
  const teile: string[] = [];
  for (const [schluessel, name] of Object.entries(NAMEN)) {
    const [k, w] = schluessel.split("=");
    if (filter.hat(k, w)) teile.push(name);
  }
  // Ein ganzer Bereich heißt wie der Bereich, Kategorien wie sie selbst, der Rest sind Regale (BF-69)
  const { namen, uebrig } = filternamen(bestand.katalog, filter.werte("category"));
  teile.push(...namen);
  for (const id of uebrig) teile.push(bestand.regal(id)?.name ?? "Regal");
  for (const id of filter.werte("sammlung")) teile.push(bestand.sammlung(id)?.name ?? "Sammlung");
  if (filter.wert("min_rating")) teile.push(filter.wert("min_rating") === "5" ? "5 Sterne" : `ab ${filter.wert("min_rating")} Sternen`);
  return teile.length ? teile.join(", ") : "Alle";
}
