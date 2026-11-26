// Katalog (BF-69): was Leiste, Bibliothek, Buchseite und Einstellungen gleich sehen. Nur Rechnen über den Daten, ohne Zustand.
import type { Herkunft, Katalog, Katalogbereich, Katalogkategorie, Kategorieregeln, RegalKurz, Regelart } from "./typen";

/** Farbe ohne eigene Angabe, wie bei den Regalen */
export const GRAUTON = "#6b7280";

/** Eine Kategorie zeigt ihre eigene Farbe, sonst die ihres Bereichs */
export function farbeVon(kategorie: { farbe?: string }, bereich?: { farbe?: string }): string {
  return kategorie.farbe || bereich?.farbe || GRAUTON;
}

/** Ist dieser Eintrag an einem Buch eine Kategorie des Katalogs (und kein Regal)? */
export function istKatalogkategorie(eintrag: RegalKurz): boolean {
  return eintrag.art === "kategorie" || (eintrag.art === undefined && !!eintrag.bereich);
}

/** Kategorien des Katalogs und Regale eines Buchs getrennt; Einträge der Bücherliste ohne Art erkennt der Katalog */
export function trenneKategorien<T extends RegalKurz>(eintraege: readonly T[], katalog: Katalog | null): { kategorien: T[]; regale: T[] } {
  const imKatalog = (e: T) => istKatalogkategorie(e) || (e.art === undefined && !!findeKategorie(katalog, e.id));
  return { kategorien: eintraege.filter(imKatalog), regale: eintraege.filter((e) => !imKatalog(e)) };
}

/** Was in der Leiste steht: Bereiche und Kategorien ohne die verborgenen */
export function sichtbareBereiche(bereiche: readonly Katalogbereich[]): Katalogbereich[] {
  return bereiche.filter((b) => !b.verborgen).map((b) => ({ ...b, kategorien: b.kategorien.filter((k) => !k.verborgen) }));
}

/** Nummern der Kategorien eines Bereichs, als Werte des Filters "category" */
export function kategorieWerte(bereich: Katalogbereich): string[] {
  return bereich.kategorien.flatMap((k) => (k.id === undefined ? [] : [String(k.id)]));
}

export function findeKategorie(katalog: Katalog | null, id: number | string): { kategorie: Katalogkategorie; bereich: Katalogbereich } | null {
  for (const bereich of katalog?.bereiche ?? []) {
    const kategorie = bereich.kategorien.find((k) => String(k.id) === String(id));
    if (kategorie) return { kategorie, bereich };
  }
  return null;
}

// Filtern in der Leiste. Ein Bereich steht für alle seine Kategorien (die Bücherliste filtert mit "kategorie" kommagetrennt);
// Regale und Kategorien anderer Bereiche bleiben gewählt, wie bei den Regalen.

/** Alle Kategorien des Bereichs sind gewählt */
export function bereichGewaehlt(bereich: Katalogbereich, gewaehlt: readonly string[]): boolean {
  const eigene = kategorieWerte(bereich);
  return eigene.length > 0 && eigene.every((w) => gewaehlt.includes(w));
}

/** Mindestens eine Kategorie des Bereichs ist gewählt: dann steht er offen */
export function bereichBeruehrt(bereich: Katalogbereich, gewaehlt: readonly string[]): boolean {
  return kategorieWerte(bereich).some((w) => gewaehlt.includes(w));
}

/** Bereich an oder aus: an heißt alle seine Kategorien */
export function schalteBereich(bereich: Katalogbereich, gewaehlt: readonly string[]): string[] {
  const eigene = kategorieWerte(bereich);
  const ohne = gewaehlt.filter((w) => !eigene.includes(w));
  return bereichGewaehlt(bereich, gewaehlt) ? ohne : [...ohne, ...eigene];
}

/** Ist der ganze Bereich gewählt, grenzt eine Kategorie ihn auf sich ein; sonst schaltet sie für sich */
export function schalteKategorie(bereich: Katalogbereich, wert: string, gewaehlt: readonly string[]): string[] {
  if (bereichGewaehlt(bereich, gewaehlt) && kategorieWerte(bereich).length > 1) {
    const eigene = kategorieWerte(bereich);
    return [...gewaehlt.filter((w) => !eigene.includes(w)), wert];
  }
  return gewaehlt.includes(wert) ? gewaehlt.filter((w) => w !== wert) : [...gewaehlt, wert];
}

/** Namen der gewählten Bereiche und Kategorien für die Überschrift; was nicht im Katalog steht, bleibt übrig */
export function filternamen(katalog: Katalog | null, gewaehlt: readonly string[]): { namen: string[]; uebrig: string[] } {
  const namen: string[] = [];
  let uebrig = [...gewaehlt];
  for (const bereich of katalog?.bereiche ?? []) {
    if (bereichGewaehlt(bereich, uebrig) && kategorieWerte(bereich).length > 1) {
      namen.push(bereich.name);
      uebrig = uebrig.filter((w) => !kategorieWerte(bereich).includes(w));
    }
  }
  for (const w of [...uebrig]) {
    const fund = findeKategorie(katalog, w);
    if (!fund) continue;
    namen.push(fund.kategorie.name);
    uebrig = uebrig.filter((x) => x !== w);
  }
  return { namen, uebrig };
}

/** Gilt ein Bereich nicht für Bücher, sagt die Kachel knapp, wofür: "gilt für Dokument, Heft" (Namen der Arten vom Server) */
export function geltungstext(arten: readonly string[] | undefined, name: (art: string) => string): string {
  if (!arten?.length || arten.includes("")) return "";
  return `gilt für ${arten.map(name).join(", ")}`;
}

// Herkunft je Kategorie, wie in der Legende

export const HERKUNFT: Record<Herkunft, [string, string]> = {
  standard: ["circle-check", "aus dem Standard"],
  geteilt: ["code-branch", "geteilt, weil groß"],
  neu: ["plus", "neu aus dem Bestand"],
  eigen: ["pen", "selbst angelegt"],
};
export const VERBORGEN: [string, string] = ["eye-slash", "verborgen, ohne Bücher"];

/** Zeichen und Name der Herkunft; verborgen geht vor */
export function herkunftszeichen(kategorie: Pick<Katalogkategorie, "herkunft" | "verborgen">): [string, string] {
  if (kategorie.verborgen) return VERBORGEN;
  return HERKUNFT[kategorie.herkunft || "eigen"] ?? HERKUNFT.eigen;
}

/** Legende: die vier aus dem Entwurf, "selbst angelegt" nur, wo es vorkommt */
export function legende(bereiche: readonly Katalogbereich[]): [string, string][] {
  const eigene = bereiche.some((b) => b.kategorien.some((k) => (k.herkunft || "eigen") === "eigen" && !k.verborgen));
  return [HERKUNFT.standard, HERKUNFT.geteilt, HERKUNFT.neu, ...(eigene ? [HERKUNFT.eigen] : []), VERBORGEN];
}

// Regeln

/** Art, Name, Zeichen; in dieser Reihenfolge stehen sie im Fenster */
export const REGELARTEN: [Regelart, string, string][] = [
  ["sachgruppen", "Sachgruppe", "layer-group"],
  ["schlagworte", "Schlagwort", "tag"],
  ["titelwoerter", "Wort im Titel", "heading"],
  ["verlage", "Verlag", "building"],
];

/** Immer alle vier Listen, ohne leere und doppelte Werte */
export function regelnAus(regeln: Partial<Kategorieregeln> | null | undefined): Kategorieregeln {
  const liste = (werte: unknown) => [...new Set((Array.isArray(werte) ? werte : []).map((w) => String(w).trim()).filter(Boolean))];
  return { sachgruppen: liste(regeln?.sachgruppen), schlagworte: liste(regeln?.schlagworte), titelwoerter: liste(regeln?.titelwoerter), verlage: liste(regeln?.verlage) };
}

/** Bereiche und Kategorien zählen, etwa für die Kachel des Standards */
export function umfang(bereiche: readonly Katalogbereich[]): { bereiche: number; kategorien: number } {
  return { bereiche: bereiche.length, kategorien: bereiche.reduce((s, b) => s + b.kategorien.length, 0) };
}
