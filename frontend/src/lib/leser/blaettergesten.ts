// Blättern mit Finger und Maus: wischen, am Rand tippen, ein Schritt je Dreh am Rad. Auswahl, Verweise und Tasten im Text
// gehen vor. Gilt für die Fläche eines Lesers und ebenso für das Dokument eines Buchrahmens.
import { istBedienbar } from "./bedienbar";

export interface Blaettergriffe {
  /** Wird gerade geblättert? Sonst gehört alles der Fläche. */
  gilt(): boolean;
  vor(): void;
  zurueck(): void;
  /** Tippen in die Mitte */
  mitte(): void;
  /** Offenes Feld oder Auswahlmenü: das Tippen gehört ihm; true, wenn es damit erledigt ist */
  belegt(): boolean;
  /** Kann die Fläche in diese Richtung noch selbst schieben (vergrößerte Seite)? */
  schiebt?(achse: "x" | "y", richtung: 1 | -1): boolean;
}

export interface Blaetterort {
  /** Der Leserahmen im Fenster, für die Ränder */
  rahmen(): { left: number; width: number };
  /** Verschiebung eines Buchrahmens gegen das Fenster */
  versatz?(): number;
}

const WISCH_AB = 40;
const TIPP_BIS = 10;
const TIPP_MS = 350;
/** So viel vom Rand zählt beim Tippen mit dem Finger */
const FINGERRAND = 0.28;
/** und so viele Punkte mit der Maus */
const MAUSRAND = 56;

export function blaettergesten(flaeche: HTMLElement | Document, ort: Blaetterort, tun: Blaettergriffe): () => void {
  const dok = flaeche.nodeType === Node.DOCUMENT_NODE ? (flaeche as Document) : (flaeche as HTMLElement).ownerDocument;
  const gewaehlt = () => dok.getSelection()?.isCollapsed === false;
  let start: { x: number; y: number; zeit: number; auswahl: boolean; schob: boolean } | null = null;

  function tippe(x: number, rand: number): void {
    if (tun.belegt()) return;
    const r = ort.rahmen();
    const im = x + (ort.versatz?.() ?? 0) - r.left;
    if (im < rand) tun.zurueck();
    else if (im > r.width - rand) tun.vor();
    else tun.mitte();
  }

  const beginnt = (e: TouchEvent) => {
    if (!tun.gilt()) return;
    start = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY, zeit: e.timeStamp, auswahl: gewaehlt(), schob: false } : null;
    e.stopPropagation();
  };

  // Waagrechtes Wischen gehört hier dem Leser, nicht dem Zurück des Browsers; eine vergrößerte Seite schiebt erst selbst
  const bewegt = (e: TouchEvent) => {
    if (!tun.gilt()) return;
    e.stopPropagation();
    if (!start || e.touches.length !== 1) {
      start = null;
      return;
    }
    const dx = e.touches[0].clientX - start.x;
    const dy = e.touches[0].clientY - start.y;
    if (gewaehlt()) return;
    // Was als Schieben begann, blättert nicht mehr, auch wenn es die Kante erreicht
    start.schob ||= Math.abs(dx) > 4 && !!tun.schiebt?.("x", dx < 0 ? 1 : -1);
    if (start.schob) return;
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10 && e.cancelable) e.preventDefault();
  };

  const endet = (e: TouchEvent) => {
    if (!tun.gilt()) return;
    e.stopPropagation();
    if (!start || e.touches.length) return;
    const { x, y, zeit, auswahl, schob } = start;
    start = null;
    const p = e.changedTouches[0];
    const [dx, dy] = [p.clientX - x, p.clientY - y];
    if (schob || gewaehlt()) return;
    if (Math.abs(dx) >= WISCH_AB && Math.abs(dx) > Math.abs(dy)) {
      if (dx < 0) tun.vor();
      else tun.zurueck();
      return;
    }
    const tipp = Math.hypot(dx, dy) < TIPP_BIS && e.timeStamp - zeit < TIPP_MS;
    if (!tipp || auswahl || istBedienbar(e.target)) return;
    // Der Klick, der dem Tippen folgt, soll nicht noch etwas treffen, das erst jetzt dort steht
    if (e.cancelable) e.preventDefault();
    tippe(p.clientX, ort.rahmen().width * FINGERRAND);
  };

  // Maus: nur die äußeren Ränder blättern, die Mitte bleibt für Auswahl und Verweise
  let maus: { x: number; y: number; auswahl: boolean } | null = null;
  const runter = (e: PointerEvent) => {
    maus = e.pointerType === "mouse" && e.button === 0 ? { x: e.clientX, y: e.clientY, auswahl: gewaehlt() } : null;
  };
  const hoch = (e: PointerEvent) => {
    const m = maus;
    maus = null;
    if (!m || !tun.gilt() || m.auswahl || gewaehlt() || Math.hypot(e.clientX - m.x, e.clientY - m.y) > TIPP_BIS || istBedienbar(e.target)) return;
    const r = ort.rahmen();
    const im = e.clientX + (ort.versatz?.() ?? 0) - r.left;
    if (im < MAUSRAND || im > r.width - MAUSRAND) tippe(e.clientX, MAUSRAND);
  };

  const rad = radschritt(tun);

  // Im Fang: der Leser kommt vor allem, was im Buch selbst auf Finger hört
  const fang = { capture: true } as const;
  const aktiv = { capture: true, passive: false } as const;
  const z = flaeche as HTMLElement;
  z.addEventListener("touchstart", beginnt, fang);
  z.addEventListener("touchmove", bewegt, aktiv);
  z.addEventListener("touchend", endet, aktiv);
  z.addEventListener("pointerdown", runter);
  z.addEventListener("pointerup", hoch);
  z.addEventListener("wheel", rad, { passive: false });
  return () => {
    z.removeEventListener("touchstart", beginnt, fang);
    z.removeEventListener("touchmove", bewegt, aktiv);
    z.removeEventListener("touchend", endet, aktiv);
    z.removeEventListener("pointerdown", runter);
    z.removeEventListener("pointerup", hoch);
    z.removeEventListener("wheel", rad);
  };
}

const RUHE_MS = 140;
const FRUEHESTENS_MS = 350;

/** Ein Schritt je Dreh: der Nachlauf eines Touchpads zählt nicht, ein kräftiger neuer Schub schon */
export function radschritt(tun: Pick<Blaettergriffe, "gilt" | "vor" | "zurueck" | "schiebt">): (e: WheelEvent) => void {
  let zuletzt = -Infinity;
  let schritt = -Infinity;
  let staerke = 0;
  return (e) => {
    if (!tun.gilt() || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const senkrecht = Math.abs(e.deltaY) >= Math.abs(e.deltaX);
    const d = senkrecht ? e.deltaY : e.deltaX;
    if (tun.schiebt?.(senkrecht ? "y" : "x", d > 0 ? 1 : -1)) {
      // Was als Schieben begann, blättert nicht mehr, auch wenn es die Kante erreicht
      zuletzt = e.timeStamp;
      schritt = e.timeStamp;
      staerke = Math.abs(d);
      return;
    }
    e.preventDefault();
    if (Math.abs(d) < 4) return;
    const neu = e.timeStamp - zuletzt > RUHE_MS || (e.timeStamp - schritt > FRUEHESTENS_MS && Math.abs(d) > staerke * 1.25);
    zuletzt = e.timeStamp;
    staerke = Math.abs(d);
    if (!neu) return;
    schritt = e.timeStamp;
    if (d > 0) tun.vor();
    else tun.zurueck();
  };
}
