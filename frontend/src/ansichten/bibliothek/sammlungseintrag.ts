// Wie eine große Sammlung als ein Eintrag der Bibliothek erscheint (BF-66)
import { anzahl, zahl } from "../../lib/format";
import type { Buch, Sammlungseintrag } from "../../lib/typen";

export const sammlungsweg = (id: number): string => `/collection/${id}`;

export const baende = (n: number): string => anzahl(n, "Band", "Bände");

/** Hinweis und Beschriftung: alles, was das Schild zeigt, in einer Zeile je Angabe */
export function sammlungshinweis(s: Sammlungseintrag): string {
  return ["Sammlung", s.name, s.autor, baende(s.anzahl)].filter(Boolean).join("\n");
}

/** Lagen im Stapel wie im Entwurf: das erste Buch vorn, das zweite ganz hinten, das dritte dazwischen */
export function stapellagen(umschlaege: Buch[]): { vorn: Buch | null; hinten: Buch | null; mitte: Buch | null } {
  return { vorn: umschlaege[0] ?? null, hinten: umschlaege[1] ?? null, mitte: umschlaege[2] ?? null };
}

/** Zahlzeile der Bibliothek: "4.734 Bücher, davon 105 in 4 Sammlungen" */
export function zahlzeile(gesamt: number, inSammlungen: number, sammlungen: number): string {
  const buecher = anzahl(gesamt, "Buch", "Bücher");
  return sammlungen > 0 ? `${buecher}, davon ${zahl(inSammlungen)} in ${anzahl(sammlungen, "Sammlung", "Sammlungen")}` : buecher;
}
