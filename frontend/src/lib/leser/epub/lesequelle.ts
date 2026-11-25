// Vorlesen aus einem EPUB oder MOBI: Einheit ist ein Abschnitt des Buchs (meist ein Kapitel). Der Text kommt aus dem Abschnitt
// selbst, auch wenn er gerade nicht gezeigt wird; gezeigt und hervorgehoben wird im Rahmen, der ihn trägt.
import type { View } from "foliate-js/view.js";
import type { Buchquelle, Satzort, Stelle, Strecke } from "../../vorlesen/typen";
import { bereichZu } from "../bereiche";
import { hebeHervor, kannHervorheben } from "../hervorhebung";
import { kapitelUm } from "../kapitelgrenzen";
import { imBlick, Mitlauf } from "../mitlauf";
import { VORLESESATZ } from "../text/lesequelle";
import { Textkarte } from "../textkarte";
import type { Kapitel } from "../typen";

export interface Epubteile {
  view: () => View | null;
  flaeche: HTMLElement;
  gescrollt: () => boolean;
  kapitel: () => Kapitel[];
  kapitelJetzt: () => number;
  /** Ersatz, wo die Hervorhebung im Rahmen fehlt: eine Markierung der Bibliothek */
  male: (bereich: Range | null) => void;
}

type Renderer = NonNullable<View["renderer"]> & { goTo(z: { index: number; anchor: (doc: Document) => Range | Element | number }): Promise<void>; scrollToAnchor(a: Range): Promise<void>; containerPosition: number; size: number };

export class Epubquelle implements Buchquelle {
  readonly einheitsart = "Abschnitt";
  #texte = new Map<number, Promise<string>>();
  #karten = new WeakMap<Document, Textkarte>();
  #jetzt: Satzort | null = null;
  #mitlauf: Mitlauf;
  #nummern: number[];

  constructor(private t: Epubteile) {
    const bahn = {
      get stand() { return (t.view()?.renderer as Renderer | undefined)?.containerPosition ?? 0; },
      set stand(w: number) { const r = t.view()?.renderer as Renderer | undefined; if (r) r.containerPosition = w; },
      get hoehe() { return (t.view()?.renderer as Renderer | undefined)?.size ?? 0; },
    };
    this.#mitlauf = new Mitlauf(bahn, t.flaeche);
    const abschnitte = (t.view()?.book?.sections ?? []) as { linear?: string }[];
    this.#nummern = abschnitte.map((_, i) => i).filter((i) => abschnitte[i].linear !== "no");
  }

  zerstoere(): void {
    this.#mitlauf.zerstoere();
  }

  get #renderer(): Renderer | null {
    return (this.t.view()?.renderer as Renderer | undefined) ?? null;
  }

  #gezeigt(): { index: number; doc: Document } | null {
    return this.#renderer?.getContents()[0] ?? null;
  }

  get anzahl(): number {
    return this.#nummern.length;
  }

  #einheitVon(index: number): number {
    return Math.max(0, this.#nummern.indexOf(index));
  }

  name(e: number): string {
    const index = this.#nummern[e];
    const view = this.t.view();
    const k = this.t.kapitel().find((x) => (view as unknown as { resolveNavigation(z: string): { index: number } | undefined })?.resolveNavigation(x.ziel as string)?.index === index);
    return k?.titel ?? `Abschnitt ${e + 1}`;
  }

  #karte(doc: Document): Textkarte {
    let k = this.#karten.get(doc);
    if (!k?.gueltig) {
      k = new Textkarte(doc.body ? [doc.body] : []);
      this.#karten.set(doc, k);
    }
    return k;
  }

  text(e: number): Promise<string> {
    let t = this.#texte.get(e);
    if (!t) {
      const index = this.#nummern[e];
      const g = this.#gezeigt();
      const abschnitt = (this.t.view()?.book?.sections as { createDocument?: () => Promise<Document> }[] | undefined)?.[index];
      t = g?.index === index ? Promise.resolve(this.#karte(g.doc).text) : (abschnitt?.createDocument?.() ?? Promise.resolve(null)).then((d) => (d ? this.#karte(d).text : "")).catch(() => "");
      this.#texte.set(e, t);
    }
    return t;
  }

  /** Bereich im gezeigten Rahmen; stimmt der Text nicht genau, über den Wortlaut */
  async #bereich(e: number, von: number, bis: number, doc?: Document): Promise<Range | null> {
    const d = doc ?? (this.#gezeigt()?.index === this.#nummern[e] ? this.#gezeigt()!.doc : null);
    if (!d?.body) return null;
    const text = await this.text(e);
    const k = this.#karte(d);
    return k.text === text ? k.bereich(von, bis) : bereichZu(d.body, text.slice(von, bis), von / Math.max(1, text.length));
  }

  markiere(ort: Satzort | null): void {
    this.#jetzt = ort;
    void (ort ? this.#bereich(ort.einheit, ort.von, ort.bis) : Promise.resolve(null)).then((b) => {
      if (this.#jetzt !== ort) return;
      const doc = this.#gezeigt()?.doc;
      if (doc && kannHervorheben(doc)) hebeHervor(doc, VORLESESATZ, b ? [b] : []);
      else this.t.male(b);
    });
  }

  /** Ein Abschnitt ist neu geladen */
  geladen(doc: Document): void {
    for (const art of ["wheel", "touchstart"]) doc.addEventListener(art, () => this.#mitlauf.vorrang(), { passive: true });
    if (this.#jetzt) this.markiere(this.#jetzt);
  }

  async fuehre(stelle: Stelle, sofort: boolean): Promise<void> {
    const r = this.#renderer;
    if (!r) return;
    const index = this.#nummern[stelle.einheit];
    const ende = stelle.zeichen + 1;
    if (this.#gezeigt()?.index !== index) {
      const text = await this.text(stelle.einheit);
      await r.goTo({ index, anchor: (doc) => this.#karte(doc).text === text ? (this.#karte(doc).bereich(stelle.zeichen, ende) ?? 0) : 0 });
      return;
    }
    const b = await this.#bereich(stelle.einheit, stelle.zeichen, ende);
    if (!b) return;
    if (!this.t.gescrollt()) {
      if (!this.#imBlick(b)) await r.scrollToAnchor(b);
      return;
    }
    const z = b.getBoundingClientRect();
    const versatz = (this.#gezeigt()!.doc.defaultView?.frameElement?.getBoundingClientRect().top ?? 0) - r.getBoundingClientRect().top;
    this.#mitlauf.folge(z.top + versatz, z.bottom + versatz, sofort);
  }

  #imBlick(b: Range): boolean {
    const rahmen = this.#gezeigt()?.doc.defaultView?.frameElement?.getBoundingClientRect();
    const f = this.t.flaeche.getBoundingClientRect();
    return imBlick(b, { oben: f.top, unten: f.bottom, links: f.left, rechts: f.right }, { x: rahmen?.left ?? 0, y: rahmen?.top ?? 0 });
  }

  sichtbar(ort: Satzort): boolean {
    const g = this.#gezeigt();
    if (!g || g.index !== this.#nummern[ort.einheit]) return false;
    const k = this.#karte(g.doc);
    const b = k.bereich(ort.von, ort.bis);
    return !!b && this.#imBlick(b);
  }

  #stelleVon(range: Range | undefined | null): Stelle | null {
    const g = this.#gezeigt();
    if (!g || !range) return null;
    const k = this.#karte(g.doc);
    return { einheit: this.#einheitVon(g.index), zeichen: k.zeichenVon(range.startContainer, range.startOffset) };
  }

  #sichtbarerBereich(): Range | null {
    return (this.t.view() as unknown as { lastLocation?: { range?: Range } })?.lastLocation?.range ?? null;
  }

  async hier(): Promise<Stelle> {
    return this.#stelleVon(this.#sichtbarerBereich()) ?? { einheit: this.#einheitVon(this.#gezeigt()?.index ?? 0), zeichen: 0 };
  }

  async seite(): Promise<Strecke> {
    const b = this.#sichtbarerBereich();
    const von = (await this.hier());
    if (!b) return { von, bis: { einheit: von.einheit + 1, zeichen: 0 } };
    const ende = b.cloneRange();
    ende.collapse(false);
    const bis = this.#stelleVon(ende);
    return { von, bis: bis && bis.zeichen > von.zeichen ? bis : { einheit: von.einheit + 1, zeichen: 0 } };
  }

  get mitKapiteln(): boolean {
    return this.t.kapitel().length > 0;
  }

  /** Anfang eines Eintrags im Verzeichnis: sein Abschnitt und, mit Sprungmarke, das Zeichen dort */
  async #anfangVon(k: Kapitel | undefined): Promise<Stelle | null> {
    const view = this.t.view() as unknown as { resolveNavigation(z: string): { index: number; anchor?: (d: Document) => Element | Range | number } | undefined } | null;
    const ziel = k && view?.resolveNavigation(k.ziel as string);
    if (!ziel || ziel.index < 0) return null;
    const einheit = this.#einheitVon(ziel.index);
    const abschnitt = (this.t.view()?.book?.sections as { createDocument?: () => Promise<Document> }[])[ziel.index];
    const doc = await abschnitt?.createDocument?.().catch(() => null);
    const marke = doc && ziel.anchor?.(doc);
    const zeichen = marke && typeof marke === "object" && "nodeType" in marke ? this.#karte(doc).zeichenVon(marke, 0) : 0;
    return { einheit, zeichen };
  }

  async kapitel(): Promise<Strecke | null> {
    const k = this.t.kapitel();
    const [anfang, naechstes] = kapitelUm(k, Math.max(0, this.t.kapitelJetzt()));
    if (anfang < 0) return null;
    const von = (await this.#anfangVon(k[anfang])) ?? (await this.hier());
    return { von, bis: naechstes === null ? null : await this.#anfangVon(k[naechstes]) };
  }

  async kapitelende(stelle: Stelle): Promise<Stelle | null> {
    for (const k of this.t.kapitel()) {
      const a = await this.#anfangVon(k);
      if (a && (a.einheit > stelle.einheit || (a.einheit === stelle.einheit && a.zeichen > stelle.zeichen))) return a;
    }
    return null;
  }
}
