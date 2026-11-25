// Was die Leser der drei Formate gemeinsam haben
import type { Markierung } from "../typen";

export interface Kapitel {
  titel: string;
  tiefe: number;
  /** Je Format: Seitenzahl, Verweis im Buch oder Anteil */
  ziel: unknown;
  /** Seitenzahl oder Prozent zum Anzeigen */
  marke?: string;
}

/** Gewählter Text im Buch, mit Ort auf dem Bildschirm und Stelle im Buch */
export interface Textauswahl {
  text: string;
  /** Mitte, obere und untere Kante, relativ zum Fenster */
  x: number;
  oben: number;
  unten: number;
  /** Stelle für eine Markierung: page:N, epubcfi(...) oder percent:N */
  cfi: string;
  /** Kurzform für Notizen: "S.41", "62%" */
  ort: string;
}

export type Feldname = "" | "inhalt" | "stellen" | "darstellung";

export const schreibweise = {
  seite: (n: number) => `S.${n}`,
  prozent: (n: number) => `${Math.round(n)}%`,
};

/** Wortlaut einer Markierung für Listen */
export function markierungstext(m: Markierung): string {
  return m.text_snippet?.trim() || "Markierung";
}

/** Stelle einer Markierung für Menschen: "Seite 41", "62 %" */
export function markierungsort(m: Markierung): string {
  const seite = m.cfi_range?.match(/^page:(\d+)/)?.[1];
  if (seite) return `Seite ${seite}`;
  const prozent = m.cfi_range?.match(/^percent:([\d.]+)/)?.[1];
  return prozent ? `${Math.round(Number(prozent))} %` : "";
}
