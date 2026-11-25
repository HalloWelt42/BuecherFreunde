// Beim Vorlesen läuft eine gescrollte Ansicht ruhig mit: die gelesene Zeile bleibt zwischen dem oberen Fünftel und der Mitte.
// Nachgeführt wird um das, was sie weitergerückt ist, also Zeile um Zeile; nur von weit her geht es ohne Übergang. Wer selbst
// scrollt, hat ein paar Sekunden Vorrang.

export interface Rollbahn {
  stand: number;
  /** Sichtbare Höhe ohne das, was Leisten verdecken */
  readonly hoehe: number;
}

const MITTE = 0.45;
const ZIEL = 0.3;
const DAUER_MS = 320;
const VORRANG_MS = 4000;

const ruhig = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export class Mitlauf {
  #ziel: number | null = null;
  #bild = 0;
  #selbst = 0;
  #loesen: () => void = () => {};

  constructor(private bahn: Rollbahn, flaeche?: EventTarget) {
    if (!flaeche) return;
    const selbst = () => this.vorrang();
    const tasten = (e: Event) => ["ArrowUp", "ArrowDown", "PageUp", "PageDown", " ", "Home", "End"].includes((e as KeyboardEvent).key) && selbst();
    flaeche.addEventListener("wheel", selbst, { passive: true });
    flaeche.addEventListener("touchstart", selbst, { passive: true });
    flaeche.addEventListener("keydown", tasten);
    this.#loesen = () => {
      flaeche.removeEventListener("wheel", selbst);
      flaeche.removeEventListener("touchstart", selbst);
      flaeche.removeEventListener("keydown", tasten);
    };
  }

  /** Der Mensch scrollt selbst */
  vorrang(): void {
    this.#selbst = Date.now();
    this.#halt();
  }

  /** oben, unten: Lage der Zeile zur Oberkante des sichtbaren Bereichs */
  folge(oben: number, unten: number, sofort: boolean): void {
    // Wer ausdrücklich hin will, hebt den Vorrang auf
    if (sofort) this.#selbst = 0;
    else if (Date.now() - this.#selbst < VORRANG_MS) return;
    const h = this.bahn.hoehe;
    const draussen = oben < 0 || unten > h;
    if (!draussen && oben <= h * MITTE && !sofort) return;
    const ziel = this.bahn.stand + (draussen || sofort ? oben - h * ZIEL : oben - h * MITTE);
    if (sofort || draussen || ruhig()) {
      this.#halt();
      this.bahn.stand = ziel;
      return;
    }
    this.#gleite(ziel);
  }

  #gleite(ziel: number): void {
    const neu = this.#ziel === null;
    this.#ziel = ziel;
    if (!neu) return;
    const start = performance.now();
    let von = this.bahn.stand;
    let zuletzt = this.#ziel;
    const schritt = (jetzt: number) => {
      if (this.#ziel === null) return;
      // Ein neues Ziel unterwegs: von hier aus weiter, ohne Ruck
      if (this.#ziel !== zuletzt) [von, zuletzt] = [this.bahn.stand, this.#ziel];
      const t = Math.min(1, (jetzt - start) / DAUER_MS);
      this.bahn.stand = von + (this.#ziel - von) * (1 - (1 - t) ** 3);
      if (t < 1) this.#bild = requestAnimationFrame(schritt);
      else this.#ziel = null;
    };
    this.#bild = requestAnimationFrame(schritt);
  }

  #halt(): void {
    cancelAnimationFrame(this.#bild);
    this.#ziel = null;
  }

  zerstoere(): void {
    this.#halt();
    this.#loesen();
  }
}

/** Die sichtbare Fläche eines Elements, ohne die Ränder, unter denen Leisten liegen */
export function sichtVon(e: HTMLElement): { oben: number; unten: number; links: number; rechts: number } {
  const r = e.getBoundingClientRect();
  const s = getComputedStyle(e);
  return { oben: r.top + (Number.parseFloat(s.paddingTop) || 0), unten: r.bottom - (Number.parseFloat(s.paddingBottom) || 0), links: r.left, rechts: r.right };
}

/** Liegt der Bereich wenigstens zum Teil in der Sicht? */
export function imBlick(bereich: Range, sicht: { oben: number; unten: number; links: number; rechts: number }, versatz = { x: 0, y: 0 }): boolean {
  for (const r of bereich.getClientRects()) {
    const [o, u, l, re] = [r.top + versatz.y, r.bottom + versatz.y, r.left + versatz.x, r.right + versatz.x];
    if (r.width && u > sicht.oben && o < sicht.unten && re > sicht.links && l < sicht.rechts) return true;
  }
  return false;
}

/** Lage eines Zeichens (Zeilenhöhe) im Fenster */
export function zeichenRechteck(knoten: Text, versatz: number): DOMRect | null {
  const r = knoten.ownerDocument.createRange();
  const v = Math.max(0, Math.min(versatz, knoten.length - 1));
  r.setStart(knoten, v);
  r.setEnd(knoten, Math.min(knoten.length, v + 1));
  for (const q of r.getClientRects()) if (q.height) return q;
  return null;
}
