// Regeln der Ergänzung: Arten, Summen und die Eigenheiten der Vorschau am Server
import type { Ergaenzungsart, Ergaenzungsregal, Ergaenzungsvorschau } from "../../../lib/api/imports";

export const ARTEN: { art: Ergaenzungsart; text: string; symbol: string; was: string }[] = [
  { art: "cover", text: "Umschläge", symbol: "image", was: "Bücher ohne Umschlag bekommen den ersten passenden aus ihrer Datei." },
  { art: "isbn", text: "ISBN", symbol: "barcode", was: "Bücher ohne ISBN werden nach einer durchsucht. Eingetragen wird nur eine ISBN, die zu Titel und Autor passt; jede andere kommt zur Wahl. Gefragt werden die Verzeichnisse nur, wenn der Text nicht reicht, und dann zu den zwei besten Funden je Buch." },
  { art: "metadaten", text: "Angaben", symbol: "cloud-arrow-down", was: "Bücher mit ISBN, denen Autor, Verlag, Jahr, Sprache, Beschreibung oder Umschlag fehlt, bekommen es aus den Verzeichnissen. Vorhandenes bleibt, die Verzeichnisse werden schonend gefragt." },
  { art: "volltext", text: "Volltext", symbol: "file-lines", was: "Alle gewählten Bücher werden geprüft, fehlender Volltext wird neu gelesen." },
];

/** Regalauswahl "Ohne Regal": am Server die 0 */
export const OHNE_REGAL = 0;

/** Wie viele Bücher drankommen. Der Volltext prüft jedes Buch; er fehlt in der Summe des Servers (Fehler 40). */
export function betroffen(v: Ergaenzungsvorschau | null, arten: Ergaenzungsart[], regal: number | null, regale: Ergaenzungsregal[]): number {
  if (!v || !arten.length) return 0;
  const volltext = arten.includes("volltext") ? (v.typen.volltext ?? 0) : 0;
  // Für "Ohne Regal" zählt die Vorschau 0, die Regalliste kennt die Zahl
  const ohne = regal === OHNE_REGAL ? (regale.find((r) => r.id === null)?.anzahl ?? 0) : 0;
  return Math.max(v.gesamt, volltext, ohne);
}

export function regalwerte(regale: Ergaenzungsregal[]): [string, string][] {
  return [["", "Alle Regale"], ...regale.map((r) => [String(r.id ?? OHNE_REGAL), `${r.id === null ? "Ohne Regal" : r.name} (${r.anzahl})`] as [string, string])];
}
