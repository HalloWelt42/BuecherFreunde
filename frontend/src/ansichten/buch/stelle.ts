// Eine Stelle im Buch, für die Suche im Buch und die Fundstellen einer ISBN (BF-111): Dateien mit Seiten springen über die Seite,
// EPUB und Text über den Anteil im Buch; so heißt die Stelle auch.
import { zahl } from "../../lib/format";
import { leseAdresse } from "../../lib/lesestand";

export interface Stelle {
  /** Dateiseite ab 1 */
  seite: number;
  /** Lage im Buch */
  prozent: number;
}

interface Buchformat {
  id: number;
  file_format: string;
}

const mitSeiten = (buch: Buchformat) => buch.file_format === "pdf";

export function stellenziel(buch: Buchformat, s: Stelle, begriff: string): string {
  return mitSeiten(buch) ? leseAdresse(buch.id, { page: s.seite, q: begriff }) : leseAdresse(buch.id, { percent: s.prozent, q: begriff });
}

export function stellenort(buch: Buchformat, s: Stelle): string {
  return mitSeiten(buch) ? `Seite ${zahl(s.seite)}` : `${s.prozent.toLocaleString("de-DE")} %`;
}
