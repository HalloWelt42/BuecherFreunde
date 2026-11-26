// Einträge der Bibliothek (BF-66): einzelne Bücher und große Sammlungen als ein Eintrag
import type { Buch, BuchListe, Eintrag } from "../typen";

/** Filter der Adresse, unter denen große Sammlungen als ein Eintrag stehen: die Ansichten Alle (kein Filter), Bücher und
 *  Dokumente (hat_isbn), die Regale und Kategorien (category) und "Ohne Kategorie" (BF-69). Jeder andere Filter sucht
 *  einzelne Bücher (Schnellfilter, Weiterlesen, Favoriten, Lesesofa, Gelesen, Ungelesen, Markiertes, Etiketten, Sammlung,
 *  Format, Bewertung): dort steht jedes Buch für sich. */
const MIT_SAMMELEINTRAG = new Set(["hat_isbn", "category", "ohne_kategorie"]);

/** Die eine Stelle, die entscheidet, ob die Liste große Sammlungen zusammenfasst */
export function fasstZusammen(gesetzt: Iterable<string>): boolean {
  for (const schluessel of gesetzt) if (!MIT_SAMMELEINTRAG.has(schluessel)) return false;
  return true;
}

export const alsEintrag = (buch: Buch): Eintrag => ({ art: "buch", buch });

/** Ohne zusammenfassen schickt der Server nur Bücher; dann ist jedes ein Eintrag */
export function eintraegeAus(antwort: BuchListe): Eintrag[] {
  return antwort.eintraege ?? antwort.buecher.map(alsEintrag);
}

/** Eindeutig über beide Arten: Buch 7 und Sammlung 7 sind zwei Einträge */
export function eintragsschluessel(e: Eintrag): string {
  return e.art === "buch" ? `b${e.buch.id}` : `s${e.sammlung.id}`;
}

/** Mehrere Seiten derselben Liste als eine */
export function verbindeSeiten(teile: BuchListe[]): BuchListe {
  return { ...teile[0], buecher: teile.flatMap((t) => t.buecher), eintraege: teile.flatMap(eintraegeAus) };
}
