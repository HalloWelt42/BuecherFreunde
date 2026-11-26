// Welches Format eines Buchs "Lesen" öffnet (BF-80), wenn es mehrere Dateien hat: je Gerät und Buch gemerkt, ohne Wahl das
// Original. Ein weiteres Format liest der Leser unter /book/:id/read/format/:format (lib/leser/lesefassung).
import { leseAdresse } from "../../lib/lesestand";
import { lies, merke, vergiss } from "../../lib/speicher";
import type { Buchdatei } from "../../lib/typen";

const schluessel = (buch: number) => `leseformat:${buch}`;

/** Das gemerkte Format, wenn das Buch es als weiteres Format hat; sonst leer (das Original) */
export function gemerktesFormat(buch: number, dateien: readonly Buchdatei[]): string {
  const f = lies(schluessel(buch));
  return dateien.some((d) => d.format === f && !d.haupt) ? f : "";
}

export function merkeFormat(buch: number, format: string, dateien: readonly Buchdatei[]): void {
  if (dateien.some((d) => d.format === format && !d.haupt)) merke(schluessel(buch), format);
  else vergiss(schluessel(buch));
}

/** Adresse des Lesers für ein weiteres Format, mit Stelle wie beim Original */
export function formatAdresse(buch: number, format: string, stelle: Record<string, string | number | undefined> = {}): string {
  return leseAdresse(buch, stelle).replace(/\/read(\?|$)/, `/read/format/${encodeURIComponent(format)}$1`);
}
