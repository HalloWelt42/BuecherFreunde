// Wohin Bücher von Hand kommen (BF-67): in eine Sammlung (mit Bandnummer und Reihenfolge) oder in ein Regal (ohne).
// Die Ansicht kennt nur diese Schnittstelle; was je Art anders ist, steht hier und nur hier.
import { bulkAction } from "../../lib/api/books";
import type { Parameter } from "../../lib/api/client";
import { setzeReihenfolge } from "../../lib/api/collections";
import { anzahl } from "../../lib/format";
import type { Buch } from "../../lib/typen";

export type Zielart = "sammlung" | "regal";

export interface Zuordnungsziel {
  art: Zielart;
  id: number;
  /** Linke Spalte, am Telefon auch der Umschalter */
  drinText: string;
  /** Wohin es zurückgeht */
  zurueck: string;
  /** Filter der Bücher, die drin sind, mit ihrer Ordnung */
  drin: Parameter;
  /** Filter des Bestands, also allem, was nicht drin ist; ohneSammlung: nur Bücher ohne Sammlung */
  uebrig(ohneSammlung: boolean): Parameter;
  /** Steht das Buch schon drin? Der Bestand einer Sammlung ohne den Schalter "Ohne Sammlung" enthält sie sonst mit */
  hat(buch: Buch): boolean;
  dazu(ids: number[]): Promise<unknown>;
  heraus(ids: number[]): Promise<unknown>;
  /** Nur, wo es eine Reihenfolge gibt (Sammlung): Bandnummern 1 bis n in dieser Folge */
  ordne?: (ids: number[]) => Promise<unknown>;
  /** Das Buch, wie es nach dem Herausnehmen ist (bis der Server es neu schickt) */
  ohne(buch: Buch): Buch;
  /** Was das Hineinnehmen anderswo nimmt, für die Rückfrage; leer: nichts, keine Frage */
  folgenDazu(buecher: Buch[]): string[];
  /** Was beim Herausnehmen von n Büchern verloren geht, für die Rückfrage */
  folgenHeraus(n: number): string[];
  /** Was rechts steht, in Worten */
  bestandText(ohneSammlung: boolean): string;
  /** Vorgabe des Schalters "Ohne Sammlung" */
  ohneSammlungVorgabe: boolean;
  /** Vorgabe des Schalters "Gleicher Autor" */
  gleicherAutorVorgabe: boolean;
}

/** n Bücher: "Das Buch ..." oder "Die Bücher ..." */
const bleiben = (n: number): string => (n === 1 ? "Das Buch selbst bleibt in der Bibliothek." : "Die Bücher selbst bleiben in der Bibliothek.");

/** Ein Buch steht in höchstens einer Sammlung: wer aus einer anderen kommt, verlässt sie samt Bandnummer */
function andereSammlungen(buecher: Buch[], id: number): string[] {
  const woher = new Map<string, number>();
  for (const b of buecher) {
    if (!b.sammlung_id || b.sammlung_id === id) continue;
    const name = b.sammlung?.name ? `die Sammlung ${b.sammlung.name}` : "ihre bisherige Sammlung";
    woher.set(name, (woher.get(name) ?? 0) + 1);
  }
  if (!woher.size) return [];
  return [...[...woher].map(([name, n]) => `${anzahl(n, "Buch verlässt", "Bücher verlassen")} ${name} samt Bandnummer.`), bleiben(buecher.length)];
}

export function sammlungsziel(id: number): Zuordnungsziel {
  return {
    art: "sammlung",
    id,
    drinText: "In der Sammlung",
    zurueck: `/collection/${id}`,
    drin: { sammlung: id, sortierung: "band", richtung: "asc" },
    uebrig: (ohneSammlung) => ({ ohne_sammlung: ohneSammlung || undefined, sortierung: "titel", richtung: "asc" }),
    hat: (b) => b.sammlung_id === id,
    // Neue Bände kommen hinten an
    dazu: (ids) => bulkAction(ids, "sammlung_zuweisen", id),
    heraus: (ids) => bulkAction(ids, "sammlung_entfernen", null),
    ordne: (ids) => setzeReihenfolge(id, ids),
    ohne: (b) => ({ ...b, sammlung_id: null, sammlung: null, band_nummer: "" }),
    folgenDazu: (buecher) => andereSammlungen(buecher, id),
    folgenHeraus: (n) => [n === 1 ? "Das Buch verliert die Sammlung und seine Bandnummer." : "Die Bücher verlieren die Sammlung und ihre Bandnummer.", bleiben(n)],
    bestandText: (ohneSammlung) => (ohneSammlung ? "ohne Sammlung" : "auch aus anderen Sammlungen"),
    ohneSammlungVorgabe: true,
    gleicherAutorVorgabe: true,
  };
}

export function regalziel(id: number): Zuordnungsziel {
  return {
    art: "regal",
    id,
    drinText: "Im Regal",
    zurueck: `/?category=${id}`,
    drin: { kategorie: id, sortierung: "titel", richtung: "asc" },
    uebrig: (ohneSammlung) => ({ nicht_kategorie: id, ohne_sammlung: ohneSammlung || undefined, sortierung: "titel", richtung: "asc" }),
    hat: (b) => b.categories.some((c) => c.id === id),
    dazu: (ids) => bulkAction(ids, "kategorie_zuweisen", id),
    heraus: (ids) => bulkAction(ids, "kategorie_entfernen", id),
    ohne: (b) => ({ ...b, categories: b.categories.filter((c) => c.id !== id) }),
    // Ein Buch darf in vielen Regalen stehen: hineinstellen nimmt nirgends etwas weg
    folgenDazu: () => [],
    folgenHeraus: (n) => [n === 1 ? "Das Buch verlässt dieses Regal, andere Regale behalten es." : "Die Bücher verlassen dieses Regal, andere Regale behalten sie.", bleiben(n)],
    bestandText: (ohneSammlung) => (ohneSammlung ? "nicht im Regal, ohne Sammlung" : "nicht im Regal"),
    ohneSammlungVorgabe: false,
    gleicherAutorVorgabe: false,
  };
}

/** Aus der Adresse /zuordnen/:art/:id; unbekannte Art oder Nummer: null */
export function zielAus(art: string, id: string): Zuordnungsziel | null {
  const nummer = Number(id);
  if (!Number.isInteger(nummer) || nummer <= 0) return null;
  return art === "sammlung" ? sammlungsziel(nummer) : art === "regal" ? regalziel(nummer) : null;
}
