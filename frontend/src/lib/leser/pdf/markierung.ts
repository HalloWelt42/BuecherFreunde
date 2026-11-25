// Markierungen und Fundstelle auf der Textebene einer PDF-Seite
import type { Markierung } from "../../typen";
import { durchsichtig, VORGABE_STIFT } from "../farben";
import { findeStuecke } from "../textsuche";

const FUNDSTELLE = "fundstelle";
const FARBE_FUNDSTELLE = "rgba(255, 152, 0, 0.45)";

function stuecke(ebene: HTMLElement): HTMLElement[] {
  return [...ebene.querySelectorAll<HTMLElement>("span")].filter((s) => !s.querySelector("span"));
}

function faerbe(spans: HTMLElement[], von: number, bis: number, farbe: string, kennung: string): void {
  for (const s of spans.slice(von, bis)) {
    if (!s.textContent?.trim()) continue;
    s.style.backgroundColor = farbe;
    s.style.borderRadius = "2px";
    s.dataset.markierung = kennung;
  }
}

export function leereEbene(ebene: HTMLElement): void {
  for (const s of ebene.querySelectorAll<HTMLElement>("span[data-markierung]")) {
    s.style.backgroundColor = "";
    s.style.borderRadius = "";
    delete s.dataset.markierung;
  }
}

export function zeichneMarkierungen(ebene: HTMLElement, seite: number, markierungen: Markierung[]): void {
  const spans = stuecke(ebene);
  const texte = spans.map((s) => s.textContent ?? "");
  for (const m of markierungen) {
    if (m.cfi_range !== `page:${seite}`) continue;
    const b = findeStuecke(texte, m.text_snippet ?? "");
    if (b) faerbe(spans, b.von, b.bis, durchsichtig(m.color || VORGABE_STIFT, 0.35), String(m.id));
  }
}

/** Färbt die Fundstelle und liefert ihr erstes Stück */
export function zeichneFundstelle(ebene: HTMLElement, wortlaut: string): HTMLElement | null {
  const spans = stuecke(ebene);
  const b = findeStuecke(spans.map((s) => s.textContent ?? ""), wortlaut);
  if (!b) return null;
  faerbe(spans, b.von, b.bis, FARBE_FUNDSTELLE, FUNDSTELLE);
  return spans[b.von];
}
