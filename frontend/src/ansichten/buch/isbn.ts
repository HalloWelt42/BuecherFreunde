// ISBN im Buch (BF-111): wie Stufen, Fundorte und Ausgaben heißen, wie die Kandidaten gruppiert und beschriftet werden. Die
// Reihenfolge kommt vom Server und bleibt; Prüfen ändert nur die Stufe in der Zeile, die Liste springt nicht.
import type { Ausgabe, Einstufung, Fundort, Fundstelle, Isbnkandidat, Isbnpruefung, Isbnsuche, Stufe } from "../../lib/api/books";
import { anzahl } from "../../lib/format";
import { stellenort } from "./stelle";

/** Klasse der Marke, Zeichen, Wort */
export const STUFEN: Record<Stufe, { klasse: string; symbol: string; wort: string }> = {
  passt: { klasse: "gut", symbol: "circle-check", wort: "passt" },
  aehnlich: { klasse: "info", symbol: "circle-half-stroke", wort: "ähnlich" },
  unbekannt: { klasse: "leise", symbol: "circle-question", wort: "unbekannt" },
  fremd: { klasse: "leise", symbol: "circle-xmark", wort: "fremd" },
};

export const FUNDORTE: Record<Fundort, string> = {
  impressum: "Impressum", rueckseite: "Rückseite", titelei: "Titelei", text: "Text", anmerkungen: "Anmerkungen", verlagsanzeige: "Verlagsanzeige", literaturliste: "Literaturliste",
};

/** "Die ISBN stammt aus der Verlagsanzeige" */
export const AUS: Record<Fundort, string> = {
  impressum: "aus dem Impressum", rueckseite: "von der Rückseite", titelei: "aus der Titelei", text: "aus dem Text", anmerkungen: "aus den Anmerkungen",
  verlagsanzeige: "aus der Verlagsanzeige", literaturliste: "aus der Literaturliste",
};

export const AUSGABEN: Record<Exclude<Ausgabe, "">, { symbol: string; wort: string }> = {
  druck: { symbol: "book", wort: "Druck" },
  ebook: { symbol: "tablet-screen-button", wort: "E-Book" },
};

/** Mehr fremde Kandidaten als so viele: nur die ersten zeigen, der Rest zugeklappt */
export const ANDERE_HOECHSTENS = 3;
export const ANDERE_ZUERST = 2;
/** Bei mehr Kandidaten als so vielen steht je Kandidat nur seine erste Fundstelle */
export const VIELE = 8;

/** Wie ein Kandidat jetzt steht: geprüft oder aus dem Text */
export interface Isbnzeile {
  kandidat: Isbnkandidat;
  pruefung: Isbnpruefung | null;
  prueft: boolean;
}

export const fremd = (k: Isbnkandidat): boolean => (k.quelle ?? k.text).stufe === "fremd";

/** Eigene oben, fremde unter "Andere Bücher"; die Reihenfolge des Servers bleibt */
export function gruppiere(kandidaten: Isbnkandidat[]): { eigen: Isbnkandidat[]; andere: Isbnkandidat[] } {
  return { eigen: kandidaten.filter((k) => !fremd(k)), andere: kandidaten.filter(fremd) };
}

/** Vorgewählt ist der beste Kandidat, der nicht fremd ist; nur fremde: keiner (BF-111) */
export function vorwahl(kandidaten: Isbnkandidat[]): string {
  return kandidaten.find((k) => !fremd(k))?.isbn ?? "";
}

export function kopfzeile(s: Isbnsuche): string {
  const zahl = s.kandidaten.length;
  return `${anzahl(zahl, "ISBN", "ISBN")} in ${anzahl(s.funde, "Fund", "Funden")}.${zahl > 1 ? " Zuerst, was zu Titel und Autor passt." : ""}`;
}

/** "3, aus Verlagsanzeige und Literaturliste", "23, aus der Literaturliste" */
export function anderezeile(andere: Isbnkandidat[]): string {
  const orte = [...new Set(andere.map((k) => k.fundort))];
  if (orte.length === 1) return `${andere.length}, ${AUS[orte[0]]}`;
  const namen = orte.map((o) => FUNDORTE[o]);
  return `${andere.length}, aus ${namen.slice(0, -1).join(", ")} und ${namen.at(-1)}`;
}

/** "auch 9783999992419 und 9 783999 992419", eine ISBN-10 als solche benannt */
export function formenzeile(k: Isbnkandidat): string {
  if (!k.formen.length) return "";
  const teile = k.formen.map((f) => (f.replace(/[^0-9Xx]/g, "").length === 10 ? `als ISBN-10 ${f}` : f));
  return `auch ${teile.length > 1 ? `${teile.slice(0, -1).join(", ")} und ${teile.at(-1)}` : teile[0]}`;
}

/** Was die Zeile zeigt: nach dem Prüfen die Quelle, wenn eine die ISBN kennt; sonst bleibt die Stufe und die Grundlage heißt
 *  "Quellen" mit "keine kennt diese ISBN" (BF-111, Entwurf Abschnitt 3) */
export function einstufung(z: Isbnzeile): Einstufung {
  if (!z.pruefung) return z.kandidat.quelle ?? z.kandidat.text;
  if (z.pruefung.einstufung) return z.pruefung.einstufung;
  return { ...z.kandidat.text, quelle: "", basis: "Quellen", was: "keine kennt diese ISBN", warum: "" };
}

/** Prüfen: offen (Knopf), fertig (ohne Knopf) oder erneut (eine Quelle ruhte) */
export function pruefstand(z: Isbnzeile): "offen" | "fertig" | "erneut" {
  if (z.kandidat.quelle && !z.pruefung) return "fertig";
  if (!z.pruefung) return "offen";
  return z.pruefung.hinweise.length && !z.pruefung.einstufung ? "erneut" : "fertig";
}

/** Die Meldung, wenn eine Quelle ruht: Klartext mit der Folge */
export function ruhemeldung(p: Isbnpruefung): string {
  const folge = p.ruht ? "Keine Quelle antwortet gerade, später noch einmal prüfen." : "Gefragt wurden die übrigen Quellen.";
  return `${p.hinweise.join(". ")}. ${folge}`;
}

/** Woher die ISBN im Buch kommt, für die Warnung im Vergleich: " Die ISBN stammt aus der Verlagsanzeige, Seite 310." */
export function fremdHerkunft(kandidat: Isbnkandidat | null, buch: { id: number; file_format: string }): string {
  const stelle = kandidat?.stellen.find((s) => s.fundort === kandidat.fundort) ?? kandidat?.stellen[0];
  if (!kandidat || !stelle) return "";
  const ort = stellenort(buch, stelle);
  return ` Die ISBN stammt ${AUS[kandidat.fundort]}, ${buch.file_format === "pdf" ? ort : `bei ${ort}`}.`;
}

/** Fundstellen je Fundort, in der Reihenfolge des Buchs (fremde Bücher stehen kurz, je Fundort eine Zeile) */
export function jeFundort(stellen: Fundstelle[]): [Fundort, Fundstelle[]][] {
  const orte = new Map<Fundort, Fundstelle[]>();
  for (const s of stellen) orte.set(s.fundort, [...(orte.get(s.fundort) ?? []), s]);
  return [...orte];
}
