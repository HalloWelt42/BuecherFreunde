// Was die Oberfläche der Lücken (BF-75) aus der Antwort des Servers rechnet, ohne Oberfläche: Zahlen der Reihe, woher die
// Zahl der Bände kommt, was eine Eingabe im Formular ändert, Platzhalter in die Suchadresse einfügen.
import type { Vorgabe } from "./annahme/vorschautypen";
import type { Gesamtangabe, Luecke, Reihe } from "./api/luecken";
import { anzahl } from "./format";

/** Erlaubte Zahl der Bände, wie am Server (models/grenzen.py, Bandzahl) */
export const BAENDE_HOECHSTENS = 9999;

/** "8 von 12" mit einer Zahl der Bände, sonst wie viele Bände da sind */
export const reihenzahl = (r: Pick<Reihe, "belegt" | "gesamt" | "buecher">): string => (r.gesamt ? `${r.belegt} von ${r.gesamt}` : anzahl(r.buecher, "Band", "Bände"));

/** Woher die geltende Zahl kommt, als kurzer Satz neben dem Feld */
export function herkunftstext(r: Pick<Reihe, "herkunft" | "quelle_gesamt" | "nachschlagen">): { text: string; symbol: string; eigen: boolean } {
  if (r.herkunft === "eigene") return { text: r.quelle_gesamt ? `eigene Angabe, die Quellen nennen ${r.quelle_gesamt}` : "eigene Angabe", symbol: "user-pen", eigen: true };
  if (r.herkunft === "keine") return { text: "ohne Zahl", symbol: "user-pen", eigen: true };
  if (r.herkunft === "quelle") return { text: "aus den Quellen", symbol: "book-atlas", eigen: false };
  const n = r.nachschlagen;
  if (n.stand === "offen") return { text: n.grund || "wird nachgeschlagen", symbol: "hourglass-half", eigen: false };
  if (n.stand === "fehler") return { text: n.grund || "die Quellen antworten nicht", symbol: "triangle-exclamation", eigen: false };
  return { text: n.grund || "die Quellen kennen keine Zahl", symbol: "book-atlas", eigen: false };
}

/** Was eine Eingabe für die Zahl der Bände ändert: leer heißt ohne Zahl, die Zahl der Quelle bleibt die der Quelle; null:
 * nichts zu ändern. Wirft bei einer Zahl, die nicht geht. */
export function gesamtAus(r: Pick<Reihe, "sprache" | "herkunft" | "gesamt" | "quelle_gesamt">, eingabe: string): Gesamtangabe | null {
  const roh = eingabe.trim();
  if (!roh) return r.herkunft === "keine" || (r.herkunft === "" && !r.gesamt) ? null : { sprache: r.sprache, wahl: "keine" };
  const zahl = Number(roh);
  if (!Number.isInteger(zahl) || zahl < 1 || zahl > BAENDE_HOECHSTENS) throw new Error(`Bände: ganze Zahl von 1 bis ${BAENDE_HOECHSTENS}`);
  if (zahl === r.gesamt && r.herkunft !== "keine") return null;
  if (r.herkunft === "quelle" && zahl === r.quelle_gesamt) return null;
  return { sprache: r.sprache, wahl: "eigene", zahl };
}

/** Was im Feld der Zahl steht: die geltende Zahl, ohne Zahl leer */
export const gesamtfeld = (r: Pick<Reihe, "gesamt">): string => (r.gesamt ? String(r.gesamt) : "");

/** Einen Platzhalter an der Schreibmarke einfügen (ersetzt eine Auswahl); liefert den Text und wo die Marke danach steht */
export function einfuegen(text: string, platzhalter: string, von: number, bis = von): { text: string; marke: number } {
  const teil = `{${platzhalter}}`;
  const a = Math.max(0, Math.min(von, text.length));
  const b = Math.max(a, Math.min(bis, text.length));
  return { text: `${text.slice(0, a)}${teil}${text.slice(b)}`, marke: a + teil.length };
}

/** Hochladen in eine Lücke über die Vorschau (BF-80): Sammlung, Band und Sprache sind gesetzt */
export const lueckenvorgabe = (sammlung: number, l: Pick<Luecke, "nummer" | "sprache">): Partial<Vorgabe> => ({ sammlung_id: sammlung, band: String(l.nummer), sprache: l.sprache });
