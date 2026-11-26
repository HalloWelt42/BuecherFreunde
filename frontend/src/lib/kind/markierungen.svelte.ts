// Private Markierungen im Kinderleser (ab Stufe Schule): ein Wort antippen, dann das letzte; die Wörter dazwischen werden
// markiert. Gespeichert wie im normalen Leser (POST /api/books/{id}/highlights, cfi_range und Wortlaut), gefunden über die
// Einheit und den Wortlaut. Der Server hält sie je Profil; die Eltern sehen sie nicht.
import { erstelleHighlight, highlightsFuerBuch, loescheHighlight } from "../api/highlights";
import type { Markierung } from "../typen";
import { lageVon, type Kinderquelle } from "./inhalt";
import type { Einheit, Wort } from "./typen";

export const STIFT = "#ffd66b";

export interface Kindermarkierung {
  id: number;
  einheit: number;
  von: number;
  bis: number;
  text: string;
}

export class Kindermarkierungen {
  liste = $state.raw<Kindermarkierung[]>([]);
  /** Anfang einer Markierung, die gerade entsteht */
  anfang = $state.raw<{ einheit: number; wort: Wort } | null>(null);
  #roh: Markierung[] = [];

  constructor(private buch: number, private quelle: Kinderquelle) {}

  async lade(): Promise<void> {
    this.#roh = await highlightsFuerBuch(this.buch);
    const aus: Kindermarkierung[] = [];
    for (const m of this.#roh) {
      const einheit = await this.quelle.einheitDer(m.cfi_range);
      if (einheit === null) continue;
      const lage = lageVon((await this.quelle.einheit(einheit)).text, m.text_snippet ?? "");
      if (lage) aus.push({ id: m.id, einheit, ...lage, text: m.text_snippet });
    }
    this.liste = aus;
  }

  /** Die Markierung, in der ein Wort steht */
  bei(einheit: number, w: Wort): Kindermarkierung | undefined {
    return this.liste.find((m) => m.einheit === einheit && w.von < m.bis && w.bis > m.von);
  }

  /** Ein Wort im Stiftmodus: erst der Anfang, dann das Ende; liefert die neue Markierung */
  async tippe(e: Einheit, w: Wort): Promise<Kindermarkierung | null> {
    const a = this.anfang;
    if (!a || a.einheit !== e.nr) {
      this.anfang = { einheit: e.nr, wort: w };
      return null;
    }
    this.anfang = null;
    const von = Math.min(a.wort.von, w.von);
    const bis = Math.max(a.wort.bis, w.bis);
    const text = e.text.slice(von, bis);
    const ort = await this.quelle.markierungsort(e.nr, von, bis);
    const neu = await erstelleHighlight(this.buch, { cfi_range: ort, color: STIFT, text_snippet: text.slice(0, 500) });
    const m = { id: neu.id, einheit: e.nr, von, bis, text };
    this.liste = [...this.liste, m];
    return m;
  }

  async entferne(m: Kindermarkierung): Promise<void> {
    await loescheHighlight(m.id);
    this.liste = this.liste.filter((x) => x.id !== m.id);
  }
}
