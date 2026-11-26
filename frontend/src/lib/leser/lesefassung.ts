// Was der Leser öffnet: das Original oder eine Übersetzung (BF-71, docs/neubau/UEBERSETZUNG.md, Lesen). Am Original hängen
// der Lesestand des Buchs, Notizen, Markierungen, Etiketten, Codestellen und die Vorlesestelle. Eine Übersetzung hat bis zum
// gemeinsamen Lesestand über die Blöcke nur ihren eigenen Lesestand (am Server getrennt gespeichert); Stellen aus ihr würden
// im Original an der falschen Stelle landen, darum bietet der Leser dort weder Notizen noch Markierungen an und merkt sich
// beim Vorlesen keine Stelle.
//
// Ebenso lesen sich ein weiteres Format des Buchs (BF-80) und lesbares Begleitmaterial (BF-81) in der App: ohne Stellen, ohne
// den Text des Servers (der gehört zum Original), mit einem Lesestand nur auf diesem Gerät.
import { alsAnhang, dateiUrl } from "../api/books";
import { ladeMaterial, materialDatei, type Material } from "../api/material";
import { lies, merke } from "../speicher";
import { fassungsdatei, holeFassungen, holeFassungslesestand, merkeFassungslesestand } from "../api/uebersetzung";
import type { Buchdatei, BuchEinzeln } from "../typen";
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
  /** Was der Server aus der Datei des Buchs las (Seitentext, Suche im Buch, gedruckte Seiten, Codestellen): nur beim Original */
  mitBuchtext: boolean;
  /** Was oben im Leser steht; ohne Angabe der Titel des Buchs */
  titel?: string;
}

/** Format des Lesers je Art des Begleitmaterials (material/arten.json am Server) */
const MATERIALFORMAT: Record<string, string> = { pdf: "pdf", epub: "epub", text: "txt", markdown: "md", bild: "bild" };

/** Lesestand nur auf diesem Gerät: für weitere Formate und Begleitmaterial führt der Server keinen */
function geraetort(pfad: string): { position: string; ort: Lesestandsort } {
  const schluessel = `lesestand:${pfad}`;
  return { position: lies(schluessel), ort: { pfad, sende: (position) => Promise.resolve(merke(schluessel, position)), uebernimm: () => {} } };
}

export function originalfassung(buch: BuchEinzeln): Lesefassung {
  return {
    fassung: null, sprache: null, format: buch.file_format, datei: dateiUrl(buch.id), anhang: alsAnhang(dateiUrl(buch.id)),
    dateiname: buch.file_name || buch.title, position: buch.reading_position ?? "", ort: buchort(buch.id), mitStellen: true, mitBuchtext: true,
  };
}

/** Ein weiteres Format des Buchs (BF-80), etwa das EPUB zu einem PDF */
export function formatfassung(buch: BuchEinzeln, d: Buchdatei): Lesefassung {
  const datei = `${dateiUrl(buch.id)}?format=${encodeURIComponent(d.format)}`;
  return { fassung: null, sprache: null, format: d.format, datei, anhang: alsAnhang(datei), dateiname: d.name, ...geraetort(`/book/${buch.id}/read/format/${d.format}`), mitStellen: false, mitBuchtext: false };
}

/** Lesbares Begleitmaterial (BF-81): PDF, EPUB, Text, Markdown, dazu Bilder; null, wenn es nicht in der App öffnet */
export function materialfassung(buch: BuchEinzeln, m: Material): Lesefassung | null {
  const format = MATERIALFORMAT[m.art];
  if (!format || !m.oeffnen) return null;
  return {
    fassung: null, sprache: null, format, datei: materialDatei(buch.id, m.id), anhang: materialDatei(buch.id, m.id, true), dateiname: m.name,
    ...geraetort(`/book/${buch.id}/material/${encodeURIComponent(m.id)}`), mitStellen: false, mitBuchtext: false, titel: `${m.name}, zu ${buch.title}`,
  };
}

export function uebersetzungsfassung(buch: BuchEinzeln, f: Uebersetzung, stand: Fassungslesestand): Lesefassung {
  const datei = fassungsdatei(f.id);
  return {
    fassung: f.id, sprache: f.sprache, format: "epub", datei, anhang: alsAnhang(datei), dateiname: true, position: stand.position,
    ort: { pfad: `/book/${buch.id}/read/${f.sprache}`, sende: (position) => merkeFassungslesestand(f.id, position), uebernimm: () => {} },
    mitStellen: false, mitBuchtext: false,
  };
}

/** Was außer dem Original gelesen werden kann: eine Übersetzung, ein weiteres Format, Begleitmaterial */
export interface Lesewahl {
  format?: string;
  material?: string;
}

/** Die Fassung zur Adresse des Lesers: ohne Angabe das Original, sonst die Übersetzung, das Format oder das Material */
export async function ladeLesefassung(buch: BuchEinzeln, sprache: string | undefined, wahl: Lesewahl = {}): Promise<Lesefassung> {
  if (wahl.material) {
    const m = (await ladeMaterial(buch.id)).material.find((x) => x.id === wahl.material);
    const f = m ? materialfassung(buch, m) : null;
    if (!f) throw new Error(m ? `${m.name} öffnet nicht in der App, nur zum Herunterladen` : "Dieses Begleitmaterial gibt es nicht");
    return f;
  }
  if (wahl.format) {
    const d = buch.dateien?.find((x) => x.format === wahl.format);
    if (!d) throw new Error(`Dieses Buch gibt es nicht als ${wahl.format.toUpperCase()}`);
    return d.haupt ? originalfassung(buch) : formatfassung(buch, d);
  }
  if (!sprache) return originalfassung(buch);
  const f = (await holeFassungen(buch.id)).find((x): x is Uebersetzung => !x.original && x.id !== null && x.sprache === sprache);
  if (!f) throw new Error("Diese Übersetzung gibt es nicht");
  return uebersetzungsfassung(buch, f, await holeFassungslesestand(f.id));
}
