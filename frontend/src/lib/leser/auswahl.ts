// Textauswahl auf einer Fläche der Seite (PDF-Textebene, Text): meldet sie nach dem Loslassen, mit dem Finger nach kurzer Ruhe
import type { Textauswahl } from "./typen";

const RUHE_MS = 350;

export function beobachteAuswahl(flaeche: HTMLElement, beschreibe: (bereich: Range) => { cfi: string; ort: string }, tun: (a: Textauswahl | null) => void): () => void {
  let gedrueckt = false;
  let uhr: ReturnType<typeof setTimeout> | undefined;

  const werteAus = () => {
    const wahl = getSelection();
    const text = wahl?.toString().trim() ?? "";
    const knoten = wahl?.anchorNode;
    if (!wahl?.rangeCount || text.length < 2 || !knoten || !flaeche.contains(knoten)) {
      tun(null);
      return;
    }
    const bereich = wahl.getRangeAt(0);
    const b = bereich.getBoundingClientRect();
    tun({ text, x: b.left + b.width / 2, oben: b.top, unten: b.bottom, ...beschreibe(bereich) });
  };
  const spaeter = (ms: number) => {
    clearTimeout(uhr);
    uhr = setTimeout(() => !gedrueckt && werteAus(), ms);
  };
  const runter = (e: PointerEvent) => {
    gedrueckt = e.pointerType === "mouse";
  };
  const hoch = () => {
    gedrueckt = false;
    spaeter(0);
  };
  const geaendert = () => {
    // Abwählen schließt sofort, nicht erst nach der Ruhe
    if (getSelection()?.isCollapsed && !gedrueckt) spaeter(120);
    else spaeter(RUHE_MS);
  };
  const gerollt = () => getSelection()?.isCollapsed === false && spaeter(120);

  flaeche.addEventListener("pointerdown", runter);
  addEventListener("pointerup", hoch);
  addEventListener("pointercancel", hoch);
  document.addEventListener("selectionchange", geaendert);
  flaeche.addEventListener("scroll", gerollt, { passive: true });
  return () => {
    clearTimeout(uhr);
    flaeche.removeEventListener("pointerdown", runter);
    removeEventListener("pointerup", hoch);
    removeEventListener("pointercancel", hoch);
    document.removeEventListener("selectionchange", geaendert);
    flaeche.removeEventListener("scroll", gerollt);
  };
}

/** Auswahl übernehmen; mit Stift gleich markieren. Liefert, ob abgewählt werden soll. */
export function nimmAuswahl(sitzung: { auswahl: Textauswahl | null; stift: boolean; stiftfarbe: string; markiere(a: Textauswahl, farbe: string): Promise<void> }, a: Textauswahl | null): boolean {
  if (!a || !sitzung.stift || !a.cfi) {
    sitzung.auswahl = a;
    return false;
  }
  sitzung.auswahl = null;
  void sitzung.markiere(a, sitzung.stiftfarbe);
  return true;
}
