// Geblättert: der Text läuft in Spalten nebeneinander, gezeigt wird immer genau ein Schirm davon. Nichts rollt, nichts gleitet.
import { alsAnker, type Lesefluss, type Ziel } from "./fluss";
import type { Anker, Rechteck, Textmass } from "./textmass";

export interface Umbruch {
  /** So weit liegen zwei Schirme auseinander */
  schritt: number;
  schirme: number;
}

/** Wer die Spalten setzt und misst; im Test nachgebaut */
export interface Spaltensatz {
  /** Spalten auf die Fläche einrichten; null, solange sie keine Größe hat */
  richteEin(): Umbruch | null;
  zeige(schirm: number, schritt: number): void;
  /** Lage eines Elements im Satz */
  lageVon(e: Element): Rechteck | null;
}

export class Blaetterfluss implements Lesefluss {
  readonly art = "blaettern";
  #umbruch: Umbruch = { schritt: 1, schirme: 1 };
  #schirm = 0;
  // Die Stelle, an der man wirklich liest. Nur ein Blättern oder Sprung setzt sie neu: wer das Gerät zweimal dreht, ist
  // wieder auf demselben Schirm.
  #halt: Anker | null = null;

  constructor(private satz: Spaltensatz, private mass: Textmass, private bewegt: () => void) {
    this.neu();
  }

  get schirm(): number {
    return this.#schirm;
  }

  get schirme(): number {
    return this.#umbruch.schirme;
  }

  get amAnfang(): boolean {
    return this.#schirm <= 0;
  }

  get amEnde(): boolean {
    return this.#schirm >= this.schirme - 1;
  }

  get anteil(): number {
    if (this.schirme <= 1) return 0;
    if (this.amEnde) return 1;
    const a = this.#halt ?? this.stelle();
    return a ? this.mass.anteil(a) : 0;
  }

  get davor(): number {
    return this.#schirm;
  }

  get danach(): number {
    return this.schirme - 1 - this.#schirm;
  }

  halt(): Anker | null {
    return this.#halt ?? this.stelle();
  }

  halteFest(): void {
    this.#halt ??= this.stelle();
  }

  vor(): boolean {
    return this.#blaettere(1);
  }

  zurueck(): boolean {
    return this.#blaettere(-1);
  }

  #blaettere(richtung: 1 | -1): boolean {
    const ziel = this.#schirm + richtung;
    if (ziel < 0 || ziel >= this.schirme) return false;
    this.#zeige(ziel);
    this.#halt = this.stelle();
    this.bewegt();
    return true;
  }

  zuAnteil(anteil: number): void {
    if (anteil <= 0 || anteil >= 1) {
      this.#zeige(anteil <= 0 ? 0 : this.schirme - 1);
      this.#halt = this.stelle();
      this.bewegt();
      return;
    }
    const a = this.mass.beiAnteil(anteil);
    if (a) this.zu(a);
  }

  zu(ziel: Ziel): void {
    const a = alsAnker(ziel, (e) => this.mass.anfangVon(e));
    const r = a ? this.mass.lage(a) : "getBoundingClientRect" in ziel && "tagName" in ziel ? this.satz.lageVon(ziel) : null;
    if (!r) return;
    this.#zeige(this.#schirmVon(r));
    this.#halt = a ?? this.stelle();
    this.bewegt();
  }

  stelle(): Anker | null {
    return this.mass.erste((r) => this.#schirmVon(r) < this.#schirm);
  }

  erreicht(e: Element): boolean {
    const r = this.satz.lageVon(e);
    return !!r && this.#schirmVon(r) <= this.#schirm;
  }

  neu(): void {
    const umbruch = this.satz.richteEin();
    if (!umbruch) return;
    this.#umbruch = umbruch;
    const r = this.#halt ? this.mass.lage(this.#halt) : null;
    this.#zeige(r ? this.#schirmVon(r) : this.#schirm);
  }

  zerstoere(): void {
    // nichts zu lösen
  }

  #schirmVon(r: Rechteck): number {
    // Ein halber Punkt Spiel: Kanten landen nach dem Teilen nicht immer auf ganzen Punkten
    return Math.max(0, Math.floor((r.links + 0.5) / this.#umbruch.schritt));
  }

  #zeige(schirm: number): void {
    this.#schirm = Math.max(0, Math.min(this.schirme - 1, schirm));
    this.satz.zeige(this.#schirm, this.#umbruch.schritt);
  }
}

/** Ab dieser Breite des Textes stehen zwei Spalten nebeneinander */
const ZWEI_SPALTEN_AB = 900;

/** Setzt den Text als CSS-Spalten in das Blatt */
export class CssSpalten implements Spaltensatz {
  constructor(private blatt: HTMLElement, private satz: HTMLElement) {}

  richteEin(): Umbruch | null {
    const s = getComputedStyle(this.blatt);
    const rand = (Number.parseFloat(s.paddingLeft) || 0) + (Number.parseFloat(s.paddingRight) || 0);
    const breite = Math.floor(this.blatt.clientWidth - rand);
    const hoehe = Math.floor(this.blatt.clientHeight - (Number.parseFloat(s.paddingTop) || 0) - (Number.parseFloat(s.paddingBottom) || 0));
    if (breite < 40 || hoehe < 40) return null;
    const spalten = breite >= ZWEI_SPALTEN_AB ? 2 : 1;
    // Die Fuge ist so breit wie beide Ränder des Blatts, darum lugt die nächste Spalte nie herein
    const fuge = Math.max(24, Math.ceil(rand));
    const spalte = Math.floor((breite - (spalten - 1) * fuge) / spalten);
    const schritt = spalten * (spalte + fuge);
    const stil = this.satz.style;
    stil.width = `${schritt - fuge}px`;
    stil.height = `${hoehe}px`;
    stil.columnWidth = `${spalte}px`;
    stil.columnGap = `${fuge}px`;
    stil.setProperty("--satzhoehe", `${hoehe}px`);
    const gesamt = Math.max(1, Math.round((this.satz.scrollWidth + fuge) / (spalte + fuge)));
    return { schritt, schirme: Math.ceil(gesamt / spalten) };
  }

  zeige(schirm: number, schritt: number): void {
    this.satz.style.transform = schirm > 0 ? `translateX(${-schirm * schritt}px)` : "";
  }

  lageVon(e: Element): Rechteck | null {
    for (const r of e.getClientRects()) if (r.width > 0 || r.height > 0) return this.imSatz(r);
    return null;
  }

  imSatz(r: DOMRect): Rechteck {
    const s = this.satz.getBoundingClientRect();
    return { links: r.left - s.left, oben: r.top - s.top, rechts: r.right - s.left, unten: r.bottom - s.top };
  }

  raeume(): void {
    for (const name of ["width", "height", "column-width", "column-gap", "transform", "--satzhoehe"]) this.satz.style.removeProperty(name);
  }
}
