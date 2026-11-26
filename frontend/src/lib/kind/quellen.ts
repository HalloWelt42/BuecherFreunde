// Welche Quelle ein Buch im Kinderleser öffnet; was sich nicht kindgerecht zeigen lässt, ergibt null
import { dateiUrl } from "../api/books";
import type { Buch } from "../typen";
import type { Kinderquelle } from "./inhalt";
import { Epubkinderquelle } from "./quelle-epub";
import { Pdfkinderquelle } from "./quelle-pdf";
import { Textkinderquelle } from "./quelle-text";

export const formatVon = (buch: Pick<Buch, "file_format">): string => buch.file_format.toLowerCase().replace(/^\./, "");

export function kannKinderleser(buch: Pick<Buch, "file_format">): boolean {
  return ["pdf", "epub", "mobi", "txt", "md"].includes(formatVon(buch));
}

/** ab: beim PDF die Seite, bei der es beginnt (die ersten Seiten kommen mit dem Öffnen) */
export async function oeffneKinderquelle(buch: Pick<Buch, "id" | "file_format">, ab = 1): Promise<Kinderquelle | null> {
  const format = formatVon(buch);
  if (format === "pdf") return Pdfkinderquelle.oeffne(buch.id, ab);
  if (format === "epub" || format === "mobi") return Epubkinderquelle.oeffne(dateiUrl(buch.id));
  if (format === "txt" || format === "md") return Textkinderquelle.oeffne(dateiUrl(buch.id), format === "md");
  return null;
}
