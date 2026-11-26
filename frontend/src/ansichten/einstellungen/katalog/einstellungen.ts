// Einstellungen des Katalogs (BF-69): je Feld Name, Einheit und die Grenzen wie am Server (models/grenzen.py)
import type { Katalogeinstellungen } from "../../../lib/typen";

export type Einstellung = keyof Katalogeinstellungen;

/** Feld, Beschriftung, kleinster und größter Wert */
export const EINSTELLUNGEN: [Einstellung, string, number, number][] = [
  ["stapel", "Titel je Stapel", 1, 20_000],
  ["ki_je_anfrage", "Bücher je Anfrage an die KI", 1, 200],
  ["sicher_ab", "Vorab angehakt ab Sicherheit %", 0, 100],
  ["teilen_ab", "Im Vorschlag teilen ab Treffern", 1, 1_000_000],
];

/** Eine ganze Zahl in den Grenzen des Felds, sonst null */
export function einstellungAus(feld: Einstellung, wert: unknown): number | null {
  const grenzen = EINSTELLUNGEN.find(([f]) => f === feld);
  const n = typeof wert === "number" ? wert : Number(String(wert ?? "").trim());
  return grenzen && Number.isInteger(n) && n >= grenzen[2] && n <= grenzen[3] ? n : null;
}
