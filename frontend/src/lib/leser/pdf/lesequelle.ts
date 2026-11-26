// Vorlesen aus einem PDF: Einheit ist die Seite, ihr Text kommt aus dem Textauszug des Servers (Absätze, ohne Kopfzeilen),
// sonst aus der Textebene. Gezeigt wird in der Ansicht, die gerade offen ist: Original oder Text.
import { textSeiten } from "../../api/books";
import type { Buchquelle, Satzort, Stelle, Strecke } from "../../vorlesen/typen";
import { bereichZu, zeichenIn } from "../bereiche";
import { hebeHervor, type Rechteckschicht } from "../hervorhebung";
import { kapitelUm } from "../kapitelgrenzen";
import { VORLESESATZ } from "../text/lesequelle";
import type { Kapitel } from "../typen";
import { seitentext, type PdfBuch } from "./dokument";
import type { Baustein } from "./textseiten.svelte";

/** Was eine Ansicht des PDF für das Vorlesen kann */
export interface Pdfansicht {
  /** Wo der Text einer Seite steht, wenn sie gerade da ist */
  wurzel(nr: number): HTMLElement | null;
  /** Die Seite zeigen und den Bereich darauf in den Blick bringen */
  zeige(nr: number, bereich: Range | null, sofort: boolean): Promise<void>;
  sichtbar(nr: number, bereich: Range | null): boolean;
  /** Seite und Wortlaut, wo man liest */
  hier(): { seite: number; wortlaut: string };
  /** Die Seiten auf dem Schirm */
  seiten(): number[];
  ersatz?(): Rechteckschicht | undefined;
}

function seitentextAus(bausteine: Baustein[]): string {
  const teile: string[] = [];
  for (const b of bausteine) {
    if (b.art === "kasten") teile.push(b.titel, ...b.inhalt.filter((t) => t.art !== "bild").map((t) => t.text));
    else if (b.art !== "bild") teile.push(b.text);
  }
  return teile.map((t) => t?.trim()).filter(Boolean).join("\n\n");
}

export class Pdfquelle implements Buchquelle {
  readonly einheitsart = "Seite";
  #texte = new Map<number, Promise<string>>();
  #jetzt: { ort: Satzort; bereich: Range | null } | null = null;

  /** buch: null, wo der Server den Text nicht kennt (weiteres Format, Begleitmaterial): dann aus der Textebene der Datei */
  constructor(private buch: number | null, private pdf: PdfBuch, private kapitelliste: () => Kapitel[], private kapitelJetzt: () => number, private ansicht: () => Pdfansicht | null) {}

  get anzahl(): number {
    return this.pdf.seiten;
  }

  name(e: number): string {
    return `Seite ${e + 1}`;
  }

  text(e: number): Promise<string> {
    let t = this.#texte.get(e);
    if (!t) {
      const vomServer = this.buch === null ? Promise.resolve("") : textSeiten(this.buch, e + 1, 1).then((a) => seitentextAus(a?.seiten?.[0]?.bausteine ?? []));
      t = vomServer
        .catch(() => "")
        .then(async (text) => text || (await seitentext(this.pdf.doc, e + 1).catch(() => "")));
      this.#texte.set(e, t);
    }
    return t;
  }

  async #bereich(ort: Satzort): Promise<Range | null> {
    const wurzel = this.ansicht()?.wurzel(ort.einheit + 1);
    const text = await this.text(ort.einheit);
    return wurzel ? bereichZu(wurzel, text.slice(ort.von, ort.bis), ort.von / Math.max(1, text.length)) : null;
  }

  markiere(ort: Satzort | null): void {
    this.#jetzt = ort && { ort, bereich: null };
    if (!ort) return this.#male(null);
    void this.#bereich(ort).then((b) => {
      if (this.#jetzt?.ort !== ort) return;
      this.#jetzt.bereich = b;
      this.#male(b);
    });
  }

  #male(b: Range | null): void {
    const dok = this.ansicht()?.wurzel(1)?.ownerDocument ?? document;
    hebeHervor(dok, VORLESESATZ, b ? [b] : [], this.ansicht()?.ersatz?.());
  }

  /** Eine Seite ist (neu) gezeichnet: der Satz darauf wird wieder hervorgehoben; ohne Nummer gilt jede */
  gezeichnet(nr?: number): void {
    if (this.#jetzt && (nr === undefined || this.#jetzt.ort.einheit + 1 === nr)) this.markiere(this.#jetzt.ort);
  }

  async fuehre(stelle: Stelle, sofort: boolean): Promise<void> {
    const a = this.ansicht();
    if (!a) return;
    const j = this.#jetzt;
    let b = j && j.ort.einheit === stelle.einheit ? j.bereich : null;
    if (b && !b.startContainer.isConnected) b = null;
    if (b && j) b = zeichenIn(b, (stelle.zeichen - j.ort.von) / Math.max(1, j.ort.bis - j.ort.von));
    await a.zeige(stelle.einheit + 1, b, sofort);
  }

  sichtbar(ort: Satzort): boolean {
    const b = this.#jetzt?.ort === ort && this.#jetzt.bereich?.startContainer.isConnected ? this.#jetzt.bereich : null;
    return this.ansicht()?.sichtbar(ort.einheit + 1, b) ?? false;
  }

  async hier(): Promise<Stelle> {
    const h = this.ansicht()?.hier() ?? { seite: 1, wortlaut: "" };
    const text = await this.text(h.seite - 1);
    const gesucht = h.wortlaut.replace(/\s+/g, " ").trim().slice(0, 40);
    const ort = gesucht ? text.replace(/\s/g, " ").indexOf(gesucht) : -1;
    return { einheit: h.seite - 1, zeichen: Math.max(0, ort) };
  }

  async seite(): Promise<Strecke> {
    const s = this.ansicht()?.seiten() ?? [1];
    return { von: { einheit: s[0] - 1, zeichen: 0 }, bis: s.at(-1)! < this.anzahl ? { einheit: s.at(-1)!, zeichen: 0 } : null };
  }

  get mitKapiteln(): boolean {
    return this.kapitelliste().length > 0;
  }

  #seiteVon(k: Kapitel | undefined): number {
    return Math.max(0, (k?.ziel as number) - 1);
  }

  async kapitel(): Promise<Strecke | null> {
    const k = this.kapitelliste();
    const [anfang, naechstes] = kapitelUm(k, Math.max(0, this.kapitelJetzt()));
    if (anfang < 0) return null;
    const von = this.#seiteVon(k[anfang]);
    // Beginnt das nächste auf derselben Seite, gilt wenigstens diese Seite
    const bis = naechstes === null ? null : Math.max(von + 1, this.#seiteVon(k[naechstes]));
    return { von: { einheit: von, zeichen: 0 }, bis: bis === null || bis >= this.anzahl ? null : { einheit: bis, zeichen: 0 } };
  }

  async kapitelende(stelle: Stelle): Promise<Stelle | null> {
    const k = this.kapitelliste();
    const [, naechstes] = kapitelUm(k, k.findLastIndex((x) => this.#seiteVon(x) <= stelle.einheit));
    return naechstes === null ? null : { einheit: Math.max(stelle.einheit + 1, this.#seiteVon(k[naechstes])), zeichen: 0 };
  }
}
