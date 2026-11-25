// Vorschlag einer Quelle gegen die Angaben des Buchs: welche Felder sich unterscheiden und was gesendet wird
import type { Aktuell, Vorschlag } from "../../lib/api/metadata";
import type { Vergleichszeile } from "../../lib/teile/Vergleichstabelle.svelte";

export type { Aktuell, Vorschlag };

/** Kennung einer Quelle oder "alle" (je Feld die beste) */
export type Quelle = string;
export const ALLE = "alle";

export const felder: [keyof Vorschlag & string, string][] = [["titel", "Titel"], ["autor", "Autor"], ["verlag", "Verlag"], ["jahr", "Jahr"], ["seiten", "Seiten"], ["isbn", "ISBN"], ["sprache", "Sprache"], ["beschreibung", "Beschreibung"]];

const text = (w: unknown) => (w === null || w === undefined ? "" : String(w));

/** Kleinschreibung ohne Satzzeichen und Akzente, zum Vergleichen */
export function grob(w: string): string {
  return w.normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

/** Nur Ziffern und X */
const ziffern = (isbn: string) => isbn.toUpperCase().replace(/[^0-9X]/g, "");

/** Dieselbe Angabe in anderer Schreibweise: ISBN mit Strichen, Namen vertauscht, Groß und klein beim Titel */
export function gleichwertig(schluessel: string, alt: string, neu: string): boolean {
  if (alt === neu) return true;
  if (schluessel === "isbn") return ziffern(alt) === ziffern(neu);
  if (schluessel === "autor") return grob(alt).split(" ").sort().join(" ") === grob(neu).split(" ").sort().join(" ") && alt.includes(",") === neu.includes(",");
  return false;
}

export function vergleiche(vorschlag: Vorschlag, aktuell: Aktuell, umschlag: string, namen: Record<string, string> = {}): Vergleichszeile[] {
  const zeilen: Vergleichszeile[] = [];
  const woher = (f: string) => namen[vorschlag.herkunft?.[f] ?? ""] ?? undefined;
  for (const [schluessel, feld] of felder) {
    const alt = text(aktuell[schluessel]);
    const neu = text(vorschlag[schluessel]);
    if (!alt && !neu) continue;
    const gleich = !neu || gleichwertig(schluessel, alt, neu);
    // Nur Groß und klein anders: wählbar, aber nicht vorgewählt
    const vorgewaehlt = !gleich && !(schluessel === "titel" && alt && grob(alt) === grob(neu));
    zeilen.push({ schluessel, feld, alt, neu: neu || alt, gewaehlt: vorgewaehlt, gleich, herkunft: neu ? woher(schluessel) : undefined });
  }
  if (vorschlag.cover_url) zeilen.push({ schluessel: "cover", feld: "Umschlag", alt: "", neu: "", gewaehlt: true, gleich: false, bildAlt: aktuell.hat_cover ? umschlag : undefined, bildNeu: vorschlag.cover_url, herkunft: woher("cover_url") });
  if (vorschlag.kategorien?.length) {
    const schon = new Set((aktuell.kategorien ?? []).map(grob));
    const dazu = vorschlag.kategorien.filter((k) => !schon.has(grob(k)));
    zeilen.push({ schluessel: "kategorien", feld: "Regale", alt: (aktuell.kategorien ?? []).join(", "), neu: dazu.length ? `dazu: ${dazu.join(", ")}` : "alle schon da", gewaehlt: dazu.length > 0, gleich: dazu.length === 0, herkunft: woher("kategorien") });
  }
  return zeilen;
}

/** Wie der Vorschlag gefunden wurde; über den Titel heißt: bitte genau ansehen */
export function fundart(v: Vorschlag): { ton: "gut" | "warn"; text: string } | null {
  if (v.fund === "isbn") return { ton: "gut", text: "Über die ISBN gefunden" };
  if (v.fund === "doi") return { ton: "gut", text: "Über die DOI im Text gefunden" };
  if (v.fund === "titel") return v.sicher ? { ton: "gut", text: "Über Titel und Autor gefunden, beide stimmen" } : { ton: "warn", text: "Über den Titel gefunden, bitte prüfen, ob es dieses Buch ist" };
  return null;
}

/** Nur Gewähltes geht an den Server; Listen aus "Alle Daten" kommen als Regale dazu */
export function nutzlast(vorschlag: Vorschlag, quelle: string, gewaehlt: Set<string>, listen: Set<string>): Record<string, unknown> {
  const daten: Record<string, unknown> = {};
  for (const [schluessel] of felder) if (gewaehlt.has(schluessel)) daten[schluessel] = vorschlag[schluessel];
  if (gewaehlt.has("cover") && vorschlag.cover_url) {
    daten.cover_url = vorschlag.cover_url;
    daten.quelle = quelle;
  }
  const regale = new Set<string>(gewaehlt.has("kategorien") ? vorschlag.kategorien : []);
  for (const name of listen) for (const wert of alsListe(vorschlag.raw?.[name])) regale.add(wert);
  if (regale.size) daten.kategorien = [...regale];
  return daten;
}

/** Eine Liste aus lauter Texten, sonst leer */
export function alsListe(wert: unknown): string[] {
  return Array.isArray(wert) && wert.length > 0 && wert.every((w) => typeof w === "string") ? (wert as string[]).filter(Boolean) : [];
}
