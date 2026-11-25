// Vorlesen aus einem Blatt (MD, TXT): Einheiten sind Stücke von ein paar Absätzen, ein neues beginnt an jeder Überschrift.
// Text und Lage kommen aus demselben Satz, darum stimmt jede Stelle zeichengenau.
import type { Buchquelle, Satzort, Stelle, Strecke } from "../../vorlesen/typen";
import type { Textfluss } from "../fluss/textfluss";
import { hebeHervor, type Hervorhebungsart, type Rechteckschicht } from "../hervorhebung";
import { kapitelUm } from "../kapitelgrenzen";
import { imBlick, Mitlauf, sichtVon, zeichenRechteck } from "../mitlauf";
import { Textkarte } from "../textkarte";
import type { Kapitel } from "../typen";

export const VORLESESATZ: Hervorhebungsart = { name: "bf-vorlesen", farbe: "rgba(240, 178, 40, 0.3)", rang: 3 };

const STUECK = 2400;
const UEBERSCHRIFT = /^H[1-3]$/;

interface Einheit {
  elemente: Element[];
  karte: Textkarte | null;
  titel: string;
}

export interface Blatteile {
  satz: HTMLElement;
  flaeche: HTMLElement;
  fluss: () => Textfluss | null;
  kapitel: () => Kapitel[];
  kapitelJetzt: () => number;
  ersatz: () => Rechteckschicht | undefined;
  /** Name eines Stücks ohne Überschrift */
  ohneTitel: (nr: number, von: number) => string;
}

export class Blattquelle implements Buchquelle {
  readonly einheitsart = "Stück";
  #einheiten: Einheit[] | null = null;
  #mitlauf: Mitlauf;

  constructor(private t: Blatteile) {
    const f = t.flaeche;
    this.#mitlauf = new Mitlauf({ get stand() { return f.scrollTop; }, set stand(w) { f.scrollTop = w; }, get hoehe() { const s = sichtVon(f); return s.unten - s.oben; } }, f);
  }

  zerstoere(): void {
    this.#mitlauf.zerstoere();
  }

  #liste(): Einheit[] {
    if (this.#einheiten && this.#einheiten.every((e) => e.elemente.every((x) => x.isConnected))) return this.#einheiten;
    const aus: Einheit[] = [];
    let titel = "";
    let laenge = 0;
    for (const e of this.t.satz.children) {
      if (e.matches("[hidden], .frueher, .mitte")) continue;
      const kopf = UEBERSCHRIFT.test(e.tagName.toUpperCase());
      if (kopf) titel = e.textContent?.trim() ?? "";
      const n = e.textContent?.length ?? 0;
      if (!aus.length || kopf || laenge + n > STUECK) {
        aus.push({ elemente: [], karte: null, titel });
        laenge = 0;
      }
      aus.at(-1)!.elemente.push(e);
      laenge += n;
    }
    return (this.#einheiten = aus);
  }

  #karte(nr: number): Textkarte | null {
    const e = this.#liste()[nr];
    if (!e) return null;
    if (!e.karte?.gueltig) e.karte = new Textkarte(e.elemente);
    return e.karte;
  }

  get anzahl(): number {
    return this.#liste().length;
  }

  name(nr: number): string {
    return this.#liste()[nr]?.titel || this.#kapitelVon(nr) || this.t.ohneTitel(nr, this.anzahl);
  }

  // Schlichter Text kennt Kapitel nur als Anteil: das letzte, das vor dem Stück beginnt
  #kapitelVon(nr: number): string {
    const k = this.t.kapitel().filter((x) => typeof x.ziel === "number");
    if (!k.length) return "";
    const laengen = this.#liste().map((_, n) => this.#karte(n)!.text.length);
    const anteil = laengen.slice(0, nr).reduce((s, l) => s + l, 0) / Math.max(1, laengen.reduce((s, l) => s + l, 0));
    return k.findLast((x) => (x.ziel as number) <= anteil + 0.0005)?.titel ?? "";
  }

  async text(nr: number): Promise<string> {
    return this.#karte(nr)?.text ?? "";
  }

  markiere(ort: Satzort | null): void {
    const r = ort && this.#karte(ort.einheit)?.bereich(ort.von, ort.bis);
    hebeHervor(this.t.satz.ownerDocument, VORLESESATZ, r ? [r] : [], this.t.ersatz());
  }

  async fuehre(stelle: Stelle, sofort: boolean): Promise<void> {
    const a = this.#karte(stelle.einheit)?.stelle(stelle.zeichen);
    const fluss = this.t.fluss();
    if (!a || !fluss) return;
    if (fluss.art === "blaettern") {
      if (!fluss.zeigt({ knoten: a.knoten, versatz: a.versatz })) fluss.zu({ knoten: a.knoten, versatz: a.versatz });
      return;
    }
    const r = zeichenRechteck(a.knoten, a.versatz);
    const s = sichtVon(this.t.flaeche);
    if (r) this.#mitlauf.folge(r.top - s.oben, r.bottom - s.oben, sofort);
  }

  sichtbar(ort: Satzort): boolean {
    const r = this.#karte(ort.einheit)?.bereich(ort.von, ort.bis);
    const fluss = this.t.fluss();
    if (!r || !fluss) return false;
    if (fluss.art === "scrollen") return imBlick(r, sichtVon(this.t.flaeche));
    const [a, b] = [this.#karte(ort.einheit)!.stelle(ort.von), this.#karte(ort.einheit)!.stelle(Math.max(ort.von, ort.bis - 1))];
    return !!((a && fluss.zeigt(a)) || (b && fluss.zeigt(b)));
  }

  #stelleVon(knoten: Node | undefined, versatz = 0): Stelle | null {
    if (!knoten) return null;
    const liste = this.#liste();
    const nr = liste.findIndex((e) => e.elemente.some((x) => x === knoten || x.contains(knoten)));
    if (nr < 0) return null;
    return { einheit: nr, zeichen: this.#karte(nr)!.zeichenVon(knoten, versatz) };
  }

  async hier(): Promise<Stelle> {
    return this.#hier();
  }

  #hier(): Stelle {
    const a = this.t.fluss()?.halt();
    return this.#stelleVon(a?.knoten, a?.versatz) ?? { einheit: 0, zeichen: 0 };
  }

  async seite(): Promise<Strecke> {
    const fluss = this.t.fluss();
    const [a, b] = [fluss?.stelle(), fluss?.ende()];
    return { von: this.#stelleVon(a?.knoten, a?.versatz) ?? this.#hier(), bis: this.#stelleVon(b?.knoten, b?.versatz) };
  }

  get mitKapiteln(): boolean {
    return this.t.kapitel().length > 0;
  }

  #anfangVon(k: Kapitel | undefined): Stelle | null {
    if (!k) return null;
    if (k.ziel instanceof Element) return this.#stelleVon(k.ziel, 0);
    // Kapitel als Anteil (schlichter Text): das Stück, in dem dieser Anteil der Zeichen liegt
    const liste = this.#liste();
    const laengen = liste.map((_, n) => this.#karte(n)!.text.length);
    let ziel = (k.ziel as number) * laengen.reduce((s, l) => s + l, 0);
    for (let n = 0; n < laengen.length; n++) {
      if (ziel < laengen[n]) return { einheit: n, zeichen: Math.floor(ziel) };
      ziel -= laengen[n];
    }
    return null;
  }

  async kapitel(): Promise<Strecke | null> {
    const k = this.t.kapitel();
    const [anfang, naechstes] = kapitelUm(k, Math.max(0, this.t.kapitelJetzt()));
    if (anfang < 0) return null;
    return { von: this.#anfangVon(k[anfang]) ?? { einheit: 0, zeichen: 0 }, bis: naechstes === null ? null : this.#anfangVon(k[naechstes]) };
  }

  async kapitelende(stelle: Stelle): Promise<Stelle | null> {
    for (const k of this.t.kapitel()) {
      const a = this.#anfangVon(k);
      if (a && (a.einheit > stelle.einheit || (a.einheit === stelle.einheit && a.zeichen > stelle.zeichen))) return a;
    }
    return null;
  }
}
