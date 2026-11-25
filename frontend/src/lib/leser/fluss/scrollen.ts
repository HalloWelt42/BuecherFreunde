// Gescrollt: ein langes Blatt. Die Stelle am oberen Rand bleibt stehen, wenn der Text neu umbricht oder vorn wächst.
import { alsAnker, type Lesefluss, type Ziel } from "./fluss";
import type { Anker, Rechteck, Textmass } from "./textmass";

/** Wer die Fläche bewegt und misst; im Test nachgebaut. Lagen zählen vom Anfang des Inhalts. */
export interface Scrollflaeche {
  stand: number;
  readonly hoehe: number;
  readonly inhalt: number;
  /** So viel verdecken die Leisten oben */
  readonly verdeckt: number;
  lageVon(e: Element): Rechteck | null;
  beiBewegung(tun: () => void): () => void;
}

const UEBERLAPP = 160;

export class Scrollfluss implements Lesefluss {
  readonly art = "scrollen";
  #halt: Anker | null = null;
  /** Lage der Stelle zum oberen Rand, damit sie genau dort bleibt */
  #versatz = 0;
  #gestellt: number | null = null;
  #ab: () => void;

  constructor(private flaeche: Scrollflaeche, private mass: Textmass, private bewegt: () => void) {
    this.#ab = flaeche.beiBewegung(() => this.#gerollt());
  }

  get #spielraum(): number {
    return Math.max(0, this.flaeche.inhalt - this.flaeche.hoehe);
  }

  get amAnfang(): boolean {
    return this.flaeche.stand <= 1;
  }

  get amEnde(): boolean {
    return this.flaeche.stand >= this.#spielraum - 2;
  }

  get anteil(): number {
    if (this.#spielraum <= 0 || this.amAnfang) return 0;
    if (this.amEnde) return 1;
    const a = this.#halt ?? this.stelle();
    return a ? this.mass.anteil(a) : 0;
  }

  get davor(): number {
    return this.flaeche.hoehe ? this.flaeche.stand / this.flaeche.hoehe : 0;
  }

  get danach(): number {
    return this.flaeche.hoehe ? (this.#spielraum - this.flaeche.stand) / this.flaeche.hoehe : 0;
  }

  halt(): Anker | null {
    return this.#halt ?? this.stelle();
  }

  halteFest(): void {
    if (!this.#halt) this.#merkeHalt();
  }

  vor(): boolean {
    return this.#schiebe(1);
  }

  zurueck(): boolean {
    return this.#schiebe(-1);
  }

  #schiebe(richtung: 1 | -1): boolean {
    if (richtung > 0 ? this.amEnde : this.amAnfang) return false;
    this.flaeche.stand += richtung * Math.max(80, this.flaeche.hoehe - UEBERLAPP);
    return true;
  }

  zuAnteil(anteil: number): void {
    if (anteil <= 0 || anteil >= 1) {
      this.flaeche.stand = anteil <= 0 ? 0 : this.#spielraum;
      this.#merkeHalt();
      this.bewegt();
      return;
    }
    const a = this.mass.beiAnteil(anteil);
    if (a) this.zu(a);
  }

  zu(ziel: Ziel): void {
    const a = alsAnker(ziel, (e) => this.mass.anfangVon(e));
    const r = a ? this.mass.lage(a) : "tagName" in ziel ? this.flaeche.lageVon(ziel) : null;
    if (!r) return;
    this.#halt = a;
    this.#versatz = this.flaeche.verdeckt;
    this.#stelle(r.oben - this.#versatz);
  }

  stelle(): Anker | null {
    const grenze = this.flaeche.stand + this.flaeche.verdeckt;
    return this.mass.erste((r) => r.unten <= grenze);
  }

  ende(): Anker | null {
    if (this.amEnde) return null;
    const grenze = this.flaeche.stand + this.flaeche.hoehe;
    return this.mass.erste((r) => r.unten <= grenze);
  }

  zeigt(a: Anker): boolean {
    const r = this.mass.lage(a);
    return !!r && r.unten > this.flaeche.stand + this.flaeche.verdeckt && r.oben < this.flaeche.stand + this.flaeche.hoehe;
  }

  erreicht(e: Element): boolean {
    const r = this.flaeche.lageVon(e);
    return !!r && r.oben < this.flaeche.stand + this.flaeche.verdeckt + 48;
  }

  neu(): void {
    const r = this.#halt ? this.mass.lage(this.#halt) : null;
    if (!r) return;
    const soll = r.oben - this.#versatz;
    // Unverändert heißt nicht anfassen: sonst stockt ein Schwung mit dem Finger
    if (Math.abs(soll - this.flaeche.stand) >= 1) this.#stelle(soll);
  }

  zerstoere(): void {
    this.#ab();
  }

  #stelle(stand: number): void {
    const vorher = this.flaeche.stand;
    this.flaeche.stand = Math.max(0, Math.min(this.#spielraum, stand));
    this.#gestellt = this.flaeche.stand;
    if (this.flaeche.stand === vorher) this.#gestellt = null;
    this.bewegt();
  }

  #gerollt(): void {
    if (this.#gestellt !== null && Math.abs(this.flaeche.stand - this.#gestellt) < 2) {
      this.#gestellt = null;
      return;
    }
    this.#gestellt = null;
    this.#merkeHalt();
    this.bewegt();
  }

  #merkeHalt(): void {
    this.#halt = this.stelle();
    const r = this.#halt ? this.mass.lage(this.#halt) : null;
    this.#versatz = r ? r.oben - this.flaeche.stand : 0;
  }
}

/** Ein scrollbares Element mit dem Blatt darin */
export class DomScrollflaeche implements Scrollflaeche {
  constructor(private element: HTMLElement) {}

  get stand(): number {
    return this.element.scrollTop;
  }
  set stand(wert: number) {
    this.element.scrollTop = wert;
  }
  get hoehe(): number {
    return this.element.clientHeight;
  }
  get inhalt(): number {
    return this.element.scrollHeight;
  }
  get verdeckt(): number {
    return Number.parseFloat(getComputedStyle(this.element).paddingTop) || 0;
  }

  lageVon(e: Element): Rechteck | null {
    for (const r of e.getClientRects()) if (r.width > 0 || r.height > 0) return this.imInhalt(r);
    return null;
  }

  imInhalt(r: DOMRect): Rechteck {
    const f = this.element.getBoundingClientRect();
    const oben = f.top - this.element.scrollTop;
    return { links: r.left - f.left, oben: r.top - oben, rechts: r.right - f.left, unten: r.bottom - oben };
  }

  beiBewegung(tun: () => void): () => void {
    let bild = 0;
    const gerollt = () => {
      cancelAnimationFrame(bild);
      bild = requestAnimationFrame(tun);
    };
    this.element.addEventListener("scroll", gerollt, { passive: true });
    return () => {
      cancelAnimationFrame(bild);
      this.element.removeEventListener("scroll", gerollt);
    };
  }
}
