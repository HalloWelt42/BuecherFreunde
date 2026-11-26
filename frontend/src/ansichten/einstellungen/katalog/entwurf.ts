// Den Entwurf eines Katalogs ändern (BF-69), ohne Zustand: jede Änderung gibt neue Bereiche zurück. Im Entwurf haben Bereiche
// und Kategorien keine Nummer; sie heißen nach ihrem festen Schlüssel, Neues bekommt einen freien.
import type { Katalogbereich, Katalogkategorie } from "../../../lib/typen";

/** Kürzel für einen Schlüssel: klein, ohne Umlaute und Zeichen, Wörter mit Bindestrich */
export function kuerzel(name: string): string {
  const ersatz: Record<string, string> = { ä: "ae", ö: "oe", ü: "ue", ß: "ss" };
  return (
    name
      .toLocaleLowerCase("de")
      .replace(/[äöüß]/g, (z) => ersatz[z])
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "neu"
  );
}

export function vergebeneSchluessel(bereiche: readonly Katalogbereich[]): Set<string> {
  return new Set(bereiche.flatMap((b) => [b.schluessel, ...b.kategorien.map((k) => k.schluessel)]));
}

/** basis, basis-2, basis-3, ... bis einer frei ist */
export function freierSchluessel(basis: string, vergeben: ReadonlySet<string>): string {
  let schluessel = basis;
  for (let n = 2; vergeben.has(schluessel); n++) schluessel = `${basis}-${n}`;
  return schluessel;
}

export function neuerBereichsschluessel(bereiche: readonly Katalogbereich[], name: string): string {
  return freierSchluessel(kuerzel(name), vergebeneSchluessel(bereiche));
}

export function neuerKategorieschluessel(bereiche: readonly Katalogbereich[], bereich: string, name: string): string {
  return freierSchluessel(`${bereich}/${kuerzel(name)}`, vergebeneSchluessel(bereiche));
}

/** Kategorie setzen: alt räumt ihre bisherige Stelle; im selben Bereich bleibt sie, wo sie stand, sonst kommt sie ans Ende */
export function setzeKategorie(bereiche: readonly Katalogbereich[], alt: string | null, ziel: string, neu: Katalogkategorie): Katalogbereich[] {
  return bereiche.map((b) => {
    const stelle = alt === null ? -1 : b.kategorien.findIndex((k) => k.schluessel === alt);
    if (b.schluessel === ziel && stelle >= 0) return { ...b, kategorien: b.kategorien.map((k, n) => (n === stelle ? neu : k)) };
    const ohne = stelle >= 0 ? b.kategorien.filter((_, n) => n !== stelle) : b.kategorien;
    return b.schluessel === ziel ? { ...b, kategorien: [...ohne, neu] } : { ...b, kategorien: ohne };
  });
}

export function entferneKategorie(bereiche: readonly Katalogbereich[], schluessel: string): Katalogbereich[] {
  return bereiche.map((b) => ({ ...b, kategorien: b.kategorien.filter((k) => k.schluessel !== schluessel) }));
}

/** Bereich setzen; seine Kategorien bleiben bei ihm. Neue Bereiche kommen ans Ende. */
export function setzeBereich(bereiche: readonly Katalogbereich[], alt: string | null, neu: Omit<Katalogbereich, "kategorien">): Katalogbereich[] {
  const stelle = alt === null ? -1 : bereiche.findIndex((b) => b.schluessel === alt);
  if (stelle < 0) return [...bereiche, { ...neu, kategorien: [] }];
  return bereiche.map((b, n) => (n === stelle ? { ...neu, kategorien: b.kategorien } : b));
}

export function entferneBereich(bereiche: readonly Katalogbereich[], schluessel: string): Katalogbereich[] {
  return bereiche.filter((b) => b.schluessel !== schluessel);
}
