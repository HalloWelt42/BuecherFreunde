// Bände in der Reihenfolge ihrer Nummer ("2" vor "10"), ohne Nummer ans Ende, sonst nach Titel
import type { Buch } from "../../lib/typen";

type Bandbuch = Pick<Buch, "band_nummer" | "title">;

const vergleich = new Intl.Collator("de", { numeric: true, sensitivity: "base" });

export function nachBand<B extends Bandbuch>(buecher: B[]): B[] {
  return [...buecher].sort((a, b) => {
    const [x, y] = [a.band_nummer?.trim() ?? "", b.band_nummer?.trim() ?? ""];
    if (!x !== !y) return x ? -1 : 1;
    return vergleich.compare(x, y) || vergleich.compare(a.title, b.title);
  });
}
