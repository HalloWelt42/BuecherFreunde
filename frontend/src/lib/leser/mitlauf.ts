// Beim Vorlesen läuft eine gescrollte Ansicht ruhig mit: die gelesene Zeile bleibt zwischen dem oberen Fünftel und der Mitte.
// Nachgeführt wird wie mit einer gedämpften Feder (BF-106): die Ansicht folgt dem Ziel gleichmäßig, ohne Ruck und ohne
// Überschwingen, auch wenn es Zeile um Zeile weiterrückt; nur von weit her geht es ohne Übergang. Wer selbst scrollt, hat ein
// paar Sekunden Vorrang.
import { festerBereich, rechteckeVon } from "./festbereich";

export interface Rollbahn {
  stand: number;
  /** Sichtbare Höhe ohne das, was Leisten verdecken */
  readonly hoehe: number;
}

const MITTE = 0.45;
const ZIEL = 0.3;
/** So träge folgt die Ansicht: kleiner folgt straffer, größer gleitet ruhiger (Sekunden bis etwa zum Ziel) */
export const GLAETTUNG_S = 0.7;
/** Näher als so viele Pixel und langsamer als so viele je Sekunde: angekommen */
const ANGEKOMMEN_PX = 0.5;
const RUHE_PX_S = 4;
const VORRANG_MS = 4000;

const ruhig = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export class Mitlauf {
  #ziel: number | null = null;
  #bild = 0;
  /** Lage und Tempo der Ansicht unterwegs, genauer als der Stand der Rollbahn (der rundet auf ganze Pixel) */
  #lage = 0;
  #tempo = 0;
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
    this.#ziel = ziel;
    if (this.#bild) return;                                   // unterwegs: es gilt nur das neue Ziel, das Tempo bleibt
    this.#lage = this.bahn.stand;
    this.#tempo = 0;
    let zuletzt = performance.now();
    const schritt = (jetzt: number) => {
      const z = this.#ziel;
      if (z === null) return void (this.#bild = 0);
      const dt = Math.min(0.1, Math.max(0, (jetzt - zuletzt) / 1000));
      zuletzt = jetzt;
      [this.#lage, this.#tempo] = feder(this.#lage, this.#tempo, z, dt);
      if (Math.abs(this.#lage - z) < ANGEKOMMEN_PX && Math.abs(this.#tempo) < RUHE_PX_S) {
        this.bahn.stand = z;
        this.#ziel = null;
        this.#bild = 0;
        return;
      }
      this.bahn.stand = this.#lage;
      this.#bild = requestAnimationFrame(schritt);
    };
    this.#bild = requestAnimationFrame(schritt);
  }

  #halt(): void {
    cancelAnimationFrame(this.#bild);
    this.#bild = 0;
    this.#ziel = null;
  }

  zerstoere(): void {
    this.#halt();
    this.#loesen();
  }
}

/** Ein Schritt einer kritisch gedämpften Feder: neue Lage und neues Tempo nach `dt` Sekunden auf dem Weg zum Ziel */
export function feder(lage: number, tempo: number, ziel: number, dt: number, glaettung = GLAETTUNG_S): [number, number] {
  const w = 2 / glaettung;
  const x = w * dt;
  const daempfung = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
  const weg = lage - ziel;
  const zug = (tempo + w * weg) * dt;
  return [ziel + (weg + zug) * daempfung, (tempo - w * zug) * daempfung];
}

/** Die sichtbare Fläche eines Elements, ohne die Ränder, unter denen Leisten liegen */
export function sichtVon(e: HTMLElement): { oben: number; unten: number; links: number; rechts: number } {
  const r = e.getBoundingClientRect();
  const s = getComputedStyle(e);
  return { oben: r.top + (Number.parseFloat(s.paddingTop) || 0), unten: r.bottom - (Number.parseFloat(s.paddingBottom) || 0), links: r.left, rechts: r.right };
}

/** Liegt der Bereich wenigstens zum Teil in der Sicht? */
export function imBlick(bereich: AbstractRange, sicht: { oben: number; unten: number; links: number; rechts: number }, versatz = { x: 0, y: 0 }): boolean {
  for (const r of rechteckeVon(bereich)) {
    const [o, u, l, re] = [r.top + versatz.y, r.bottom + versatz.y, r.left + versatz.x, r.right + versatz.x];
    if (r.width && u > sicht.oben && o < sicht.unten && re > sicht.links && l < sicht.rechts) return true;
  }
  return false;
}

/** Lage eines Zeichens (Zeilenhöhe) im Fenster; gemessen ohne neuen mitlaufenden Bereich, auch tausendmal je Bild */
export function zeichenRechteck(knoten: Text, versatz: number): DOMRect | null {
  const v = Math.max(0, Math.min(versatz, knoten.length - 1));
  for (const q of rechteckeVon(festerBereich({ knoten, versatz: v }, { knoten, versatz: Math.min(knoten.length, v + 1) }))) if (q.height) return q;
  return null;
}
