// Ein EPUB oder MOBI im Kinderleser, geöffnet mit derselben Bibliothek wie im normalen Leser (foliate-js), aber ohne ihre
// Ansicht: Einheit ist ein Abschnitt des Buchs in Lesefolge (wie lib/leser/epub/lesequelle.ts), sein Text kommt über die
// Textkarte des normalen Lesers, die Bilder mit den Adressen, die die Bibliothek beim Laden vergibt. Stellen und Markierungen
// werden als CFI geschrieben, wie der normale Leser sie schreibt und liest.
import type { FoliateAbschnitt, FoliateBuch } from "foliate-js/view.js";
import { anfrage } from "../api/client";
import type { Lesewerte } from "../lesestand";
import { Textkarte } from "../leser/textkarte";
import { einheitAusText, type Kinderquelle } from "./inhalt";
import type { Bild, Einheit, Kinderstelle } from "./typen";

const TITEL = "h1, h2, h3, h4, h5, h6";
const XLINK = "http://www.w3.org/1999/xlink";

interface Geladen {
  einheit: Einheit;
  doc: Document;
  karte: Textkarte;
}

async function dokumentAus(adresse: string): Promise<Document> {
  const antwort = await fetch(adresse);
  const roh = await antwort.text();
  const art = antwort.headers.get("content-type")?.split(";")[0] || "application/xhtml+xml";
  const parser = new DOMParser();
  const doc = parser.parseFromString(roh, art.includes("xml") ? (art as DOMParserSupportedType) : "text/html");
  return doc.querySelector("parsererror") ? parser.parseFromString(roh, "text/html") : doc;
}

function bilderAus(doc: Document, karte: Textkarte): { von: number; bild: Bild }[] {
  const aus: { von: number; bild: Bild }[] = [];
  for (const e of doc.querySelectorAll("img, image")) {
    const adresse = e.getAttribute("src") ?? e.getAttribute("href") ?? e.getAttributeNS(XLINK, "href") ?? "";
    if (!adresse || !/^(blob:|data:)/.test(adresse)) continue;
    const breite = Number(e.getAttribute("width")) || 0;
    const hoehe = Number(e.getAttribute("height")) || 0;
    aus.push({ von: karte.zeichenVon(e, 0), bild: { adresse, verhaeltnis: breite && hoehe ? breite / hoehe : null, text: e.getAttribute("alt") ?? "" } });
  }
  return aus;
}

export class Epubkinderquelle implements Kinderquelle {
  readonly art = "epub";
  #geladen = new Map<number, Promise<Geladen>>();
  #cfi: typeof import("foliate-js/epubcfi.js") | null = null;

  private constructor(private buch: FoliateBuch, private nummern: number[]) {}

  /** adresse: die Datei des Buchs */
  static async oeffne(adresse: string): Promise<Epubkinderquelle> {
    const [{ makeBook }, cfi, antwort] = await Promise.all([import("foliate-js/view.js"), import("foliate-js/epubcfi.js"), anfrage(adresse)]);
    const buch = await makeBook(new File([await antwort.blob()], "buch.epub", { type: "application/epub+zip" }));
    const abschnitte = buch.sections ?? [];
    const q = new Epubkinderquelle(buch, abschnitte.map((_, i) => i).filter((i) => abschnitte[i]?.linear !== "no"));
    q.#cfi = cfi;
    return q;
  }

  get anzahl(): number {
    return this.nummern.length;
  }

  #abschnitt(einheit: number): FoliateAbschnitt | undefined {
    return this.buch.sections[this.nummern[einheit]];
  }

  name(einheit: number): string {
    return `Abschnitt ${einheit + 1}`;
  }

  #lade(nr: number): Promise<Geladen> {
    let g = this.#geladen.get(nr);
    if (!g) {
      g = (async () => {
        const a = this.#abschnitt(nr);
        const adresse = await a?.load();
        const doc = adresse ? await dokumentAus(adresse) : document.implementation.createHTMLDocument("");
        const karte = new Textkarte(doc.body ? [doc.body] : []);
        const istTitel = (von: number) => !!karte.stelle(von)?.knoten.parentElement?.closest(TITEL);
        return { doc, karte, einheit: einheitAusText(nr, karte.text, istTitel, bilderAus(doc, karte)) };
      })();
      g.catch(() => this.#geladen.delete(nr));
      this.#geladen.set(nr, g);
    }
    return g;
  }

  async einheit(nr: number): Promise<Einheit> {
    return (await this.#lade(nr)).einheit;
  }

  #basis(einheit: number): string {
    const index = this.nummern[einheit];
    return this.#abschnitt(einheit)?.cfi ?? this.#cfi!.fake.fromIndex(index);
  }

  async #cfiVon(einheit: number, von: number, bis: number): Promise<string> {
    const { karte } = await this.#lade(einheit);
    const bereich = karte.bereich(von, bis);
    return bereich ? this.#cfi!.joinIndir(this.#basis(einheit), this.#cfi!.fromRange(bereich)) : this.#basis(einheit);
  }

  async lesewerte(stelle: Kinderstelle): Promise<Lesewerte> {
    const { einheit } = await this.#lade(stelle.einheit);
    const anteil = (stelle.einheit + (einheit.text.length ? stelle.zeichen / einheit.text.length : 0)) / Math.max(1, this.anzahl);
    return { cfi: await this.#cfiVon(stelle.einheit, stelle.zeichen, stelle.zeichen), percent: Math.round(anteil * 1000) / 10 };
  }

  /** Abschnitt und Zeichen zu einer CFI des normalen Lesers */
  async #stelleZu(cfi: string): Promise<Kinderstelle | null> {
    const ziel = this.buch.resolveCFI?.(cfi);
    const einheit = ziel ? this.nummern.indexOf(ziel.index) : -1;
    if (!ziel || einheit < 0) return null;
    const { doc, karte } = await this.#lade(einheit);
    const anker = ziel.anchor?.(doc);
    if (anker && typeof anker === "object" && "startContainer" in anker) return { einheit, zeichen: karte.zeichenVon(anker.startContainer, anker.startOffset) };
    if (anker && typeof anker === "object" && "nodeType" in anker) return { einheit, zeichen: karte.zeichenVon(anker, 0) };
    return { einheit, zeichen: 0 };
  }

  async stelleAus(werte: Lesewerte): Promise<Kinderstelle | null> {
    if (werte.cfi) {
      const s = await this.#stelleZu(werte.cfi).catch(() => null);
      if (s) return s;
    }
    if (typeof werte.percent === "number") return { einheit: Math.min(this.anzahl - 1, Math.floor((werte.percent / 100) * this.anzahl)), zeichen: 0 };
    return null;
  }

  markierungsort(einheit: number, von: number, bis: number): Promise<string> {
    return this.#cfiVon(einheit, von, bis);
  }

  async einheitDer(ort: string): Promise<number | null> {
    try {
      const ziel = this.buch.resolveCFI?.(ort);
      const einheit = ziel ? this.nummern.indexOf(ziel.index) : -1;
      return einheit >= 0 ? einheit : null;
    } catch {
      return null;
    }
  }

  ort(stelle: Kinderstelle): string {
    return `${Math.round(((stelle.einheit + 0.5) / Math.max(1, this.anzahl)) * 100)}%`;
  }

  schliesse(): void {
    for (const nr of this.#geladen.keys()) this.#abschnitt(nr)?.unload?.();
    this.#geladen.clear();
    this.buch.destroy?.();
  }
}
