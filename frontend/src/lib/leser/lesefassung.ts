// Was der Leser öffnet: das Original oder eine Übersetzung (BF-71, docs/neubau/UEBERSETZUNG.md, Lesen). Am Original hängen
// der Lesestand des Buchs, Notizen, Markierungen, Etiketten, Codestellen und die Vorlesestelle. Eine Übersetzung hat bis zum
// gemeinsamen Lesestand über die Blöcke nur ihren eigenen Lesestand (am Server getrennt gespeichert); Stellen aus ihr würden
// im Original an der falschen Stelle landen, darum bietet der Leser dort weder Notizen noch Markierungen an und merkt sich
// beim Vorlesen keine Stelle.
import { alsAnhang, dateiUrl } from "../api/books";
import { fassungsdatei, holeFassungen, holeFassungslesestand, merkeFassungslesestand } from "../api/uebersetzung";
import type { BuchEinzeln } from "../typen";
import type { Fassungslesestand, Uebersetzung } from "../uebersetzung/typen";
import { buchort, type Lesestandsort } from "./position";

export interface Lesefassung {
  /** null: das Original */
  fassung: number | null;
  /** Sprache der Übersetzung; null beim Original */
  sprache: string | null;
  /** Format der Datei, die der Leser öffnet */
  format: string;
  /** Die Datei zum Lesen */
  datei: string;
  /** Dieselbe Datei zum Herunterladen */
  anhang: string;
  /** Name beim Herunterladen; true: wie der Server sie nennt */
  dateiname: string | true;
  /** Lesestand beim Öffnen */
  position: string;
  /** Wohin der Lesestand geht */
  ort: Lesestandsort;
  /** Notizen, Markierungen, Etiketten, Codestellen und Vorlesestelle gehören hierher: nur beim Original */
  mitStellen: boolean;
}

export function originalfassung(buch: BuchEinzeln): Lesefassung {
  return {
    fassung: null, sprache: null, format: buch.file_format, datei: dateiUrl(buch.id), anhang: alsAnhang(dateiUrl(buch.id)),
    dateiname: buch.file_name || buch.title, position: buch.reading_position ?? "", ort: buchort(buch.id), mitStellen: true,
  };
}

export function uebersetzungsfassung(buch: BuchEinzeln, f: Uebersetzung, stand: Fassungslesestand): Lesefassung {
  const datei = fassungsdatei(f.id);
  return {
    fassung: f.id, sprache: f.sprache, format: "epub", datei, anhang: alsAnhang(datei), dateiname: true, position: stand.position,
    ort: { pfad: `/book/${buch.id}/read/${f.sprache}`, sende: (position) => merkeFassungslesestand(f.id, position), uebernimm: () => {} },
    mitStellen: false,
  };
}

/** Die Fassung zur Adresse des Lesers: ohne Sprache das Original, sonst die Übersetzung in diese Sprache */
export async function ladeLesefassung(buch: BuchEinzeln, sprache: string | undefined): Promise<Lesefassung> {
  if (!sprache) return originalfassung(buch);
  const f = (await holeFassungen(buch.id)).find((x): x is Uebersetzung => !x.original && x.id !== null && x.sprache === sprache);
  if (!f) throw new Error("Diese Übersetzung gibt es nicht");
  return uebersetzungsfassung(buch, f, await holeFassungslesestand(f.id));
}
