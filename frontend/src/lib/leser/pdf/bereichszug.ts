// Ein Rechteck auf einer Seite des PDF ziehen (BF-123): Drücken auf der Seite, Ziehen, Loslassen. Mit der Maus immer (eine
// gescannte Seite hat sonst nichts zum Ziehen), mit Finger oder Stift nur, wenn `darf` es erlaubt (Markierstift an), sonst rollt
// der Finger die Seite. Was bedient wird (Links, Tasten der Codestellen), geht vor.
import { istBedienbar } from "../bedienbar";
import { bereichZwischen, type Bereich } from "./bereich";

export interface Zuggriffe {
  darf(e: PointerEvent): boolean;
  /** Während des Ziehens: das Rechteck, wie es gerade ist (null: noch zu klein oder vorbei) */
  zieht(zug: { seite: number; lage: Bereich } | null): void;
  /** Losgelassen mit einem Rechteck, das groß genug ist; rahmen ist die Seite im Fenster */
  fertig(seite: number, lage: Bereich, rahmen: DOMRect): void;
}

export function bereichszug(flaeche: HTMLElement, tun: Zuggriffe): () => void {
  let start: { id: number; seite: number; rahmen: DOMRect; x: number; y: number } | null = null;

  const runter = (e: PointerEvent) => {
    if (e.button > 0 || !tun.darf(e) || istBedienbar(e.target)) return;
    const blatt = (e.target as Element | null)?.closest?.<HTMLElement>(".pdfseite");
    const seite = Number(blatt?.dataset.seite);
    if (!blatt || !seite) return;
    start = { id: e.pointerId, seite, rahmen: blatt.getBoundingClientRect(), x: e.clientX, y: e.clientY };
    flaeche.setPointerCapture?.(e.pointerId);
    if (e.pointerType === "mouse") e.preventDefault();
  };
  const lage = (e: PointerEvent) => (start ? bereichZwischen(start.rahmen, { x: start.x, y: start.y }, { x: e.clientX, y: e.clientY }) : null);
  const zieht = (e: PointerEvent) => {
    if (!start || e.pointerId !== start.id) return;
    const b = lage(e);
    tun.zieht(b && { seite: start.seite, lage: b });
  };
  const hoch = (e: PointerEvent) => {
    if (!start || e.pointerId !== start.id) return;
    const b = lage(e);
    const { seite, rahmen } = start;
    start = null;
    tun.zieht(null);
    if (b) tun.fertig(seite, b, rahmen);
  };
  const ab = () => {
    start = null;
    tun.zieht(null);
  };
  flaeche.addEventListener("pointerdown", runter);
  flaeche.addEventListener("pointermove", zieht);
  flaeche.addEventListener("pointerup", hoch);
  flaeche.addEventListener("pointercancel", ab);
  return () => {
    flaeche.removeEventListener("pointerdown", runter);
    flaeche.removeEventListener("pointermove", zieht);
    flaeche.removeEventListener("pointerup", hoch);
    flaeche.removeEventListener("pointercancel", ab);
  };
}
