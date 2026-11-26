// PDF laden: pdf.js erst bei Bedarf, dazu Maß der ersten Seite, Verzeichnis und gedruckte Seitenzahlen
import type { PDFDocumentProxy } from "pdfjs-dist";
import { getToken } from "../../api/client";
import type { Kapitel } from "../typen";
import type { Mass } from "./zoom";

type PdfJs = typeof import("pdfjs-dist");

export interface PdfBuch {
  lib: PdfJs;
  doc: PDFDocumentProxy;
  seiten: number;
  mass: Mass;
  /** Gedruckte Seitenzahlen aus der Datei, falls sie welche nennt */
  beschriftung: string[] | null;
}

/** Die Datei unter dieser Adresse: das Buch, ein weiteres Format oder Begleitmaterial (lib/leser/lesefassung) */
export async function ladePdf(adresse: string): Promise<PdfBuch> {
  const lib = (await import("pdfjs-dist/legacy/build/pdf.mjs")) as unknown as PdfJs;
  lib.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/legacy/build/pdf.worker.min.mjs", import.meta.url).href;
  // Rechenfunktionen im PDF ohne eval: die Content-Security-Policy (BF-5) lässt keinen Code aus Zeichenketten zu
  const doc = await lib.getDocument({ url: adresse, httpHeaders: { Authorization: `Bearer ${getToken()}` }, isEvalSupported: false }).promise;
  const blick = (await doc.getPage(1)).getViewport({ scale: 1 });
  const beschriftung = await doc.getPageLabels().catch(() => null);
  return { lib, doc, seiten: doc.numPages, mass: { breite: blick.width, hoehe: blick.height }, beschriftung };
}

export function gedruckteSeite(buch: PdfBuch, nr: number): string {
  const b = buch.beschriftung?.[nr - 1] ?? "";
  return b && b !== String(nr) ? b : "";
}

interface Knoten {
  title: string;
  dest: string | unknown[] | null;
  items: Knoten[];
}

async function seiteVon(doc: PDFDocumentProxy, ziel: string | unknown[] | null): Promise<number | null> {
  try {
    const aufgeloest = typeof ziel === "string" ? await doc.getDestination(ziel) : ziel;
    const verweis = aufgeloest?.[0];
    if (typeof verweis === "number") return verweis + 1;
    return verweis ? (await doc.getPageIndex(verweis as Parameters<PDFDocumentProxy["getPageIndex"]>[0])) + 1 : null;
  } catch {
    return null;
  }
}

/** Inhaltsverzeichnis der Datei, flach mit Tiefe; leer, wenn sie keines hat */
export async function verzeichnis(doc: PDFDocumentProxy): Promise<Kapitel[]> {
  const aus: Kapitel[] = [];
  const geh = async (knoten: Knoten[], tiefe: number): Promise<void> => {
    for (const k of knoten) {
      const seite = await seiteVon(doc, k.dest);
      if (seite) aus.push({ titel: k.title.trim() || "Ohne Titel", tiefe, ziel: seite, marke: String(seite) });
      if (k.items?.length) await geh(k.items, tiefe + 1);
    }
  };
  const wurzel = (await doc.getOutline().catch(() => null)) as Knoten[] | null;
  if (wurzel) await geh(wurzel, 0);
  return aus;
}

export async function seitentext(doc: PDFDocumentProxy, nr: number): Promise<string> {
  const inhalt = await (await doc.getPage(nr)).getTextContent();
  return inhalt.items.map((i) => ("str" in i ? i.str : "")).join(" ");
}
