// Hülle um die EPUB-Bibliothek: öffnen, blättern, springen, Stile, Markierungen, Suche, Auswahl
import type { FoliateKapitel, FoliateStand, View } from "foliate-js/view.js";
import { dateiUrl } from "../../api/books";
import { anfrage } from "../../api/client";
import type { Markierung } from "../../typen";
import { VORGABE_STIFT } from "../farben";
import type { Kapitel } from "../typen";
import { leseschriftenCss } from "./schriften";
import { breite, epubCss, randfarbe, setzeStil, type Epubdarstellung } from "./stile";

export interface Epubstand {
  anteil: number;
  cfi: string;
  kapitel: string;
  kapitelNr: number;
  /** Seite der gedruckten Ausgabe, wenn das Buch ein Seitenverzeichnis hat */
  gedruckt: string;
}

export interface Epubgriffe {
  beiStand(stand: Epubstand): void;
  beiAuswahl(a: { text: string; cfi: string; x: number; oben: number; unten: number } | null): void;
  beiTaste(e: KeyboardEvent): void;
}

const RAND = "32px";
const RUHE_AUSWAHL_MS = 350;

function flach(toc: FoliateKapitel[], tiefe = 0): Kapitel[] {
  return toc.flatMap((k) => [{ titel: k.label?.trim() || "Ohne Titel", tiefe, ziel: k.href }, ...flach(k.subitems ?? [], tiefe + 1)]);
}

export class EpubAnzeige {
  kapitel: Kapitel[] = [];
  treffer: string[] = [];
  #view: View | null = null;
  #markierungen: Markierung[] = [];
  #schriften = leseschriftenCss();
  #uhr: ReturnType<typeof setTimeout> | undefined;

  constructor(private flaeche: HTMLElement, private darstellung: Epubdarstellung, private griffe: Epubgriffe) {}

  async oeffne(id: number, cfi: string): Promise<void> {
    const [{ View }, { Overlayer }, antwort] = await Promise.all([import("foliate-js/view.js"), import("foliate-js/overlayer.js"), anfrage(dateiUrl(id))]);
    const datei = new File([await antwort.blob()], "buch.epub", { type: "application/epub+zip" });
    const view = new View();
    this.#view = view;
    view.style.cssText = "display: block; width: 100%; height: 100%;";
    this.flaeche.replaceChildren(view);
    await view.open(datei);
    this.kapitel = flach(view.book?.toc ?? []);
    view.addEventListener("draw-annotation", (e) => {
      const { draw, annotation } = (e as CustomEvent).detail;
      draw(Overlayer.highlight, { color: annotation.color ?? this.#markierungen.find((m) => m.cfi_range === annotation.value)?.color ?? VORGABE_STIFT });
    });
    view.addEventListener("load", (e) => this.#geladen((e as CustomEvent).detail));
    view.addEventListener("relocate", (e) => this.#gerueckt((e as CustomEvent<FoliateStand>).detail));
    this.#seitenmass();
    await view.init({ lastLocation: cfi || undefined });
    this.stile(this.darstellung);
  }

  schliesse(): void {
    clearTimeout(this.#uhr);
    this.#view?.close();
    this.#view?.remove();
    this.#view = null;
  }

  #sprache(): string {
    const s = this.#view?.book?.metadata?.language;
    return (Array.isArray(s) ? s[0] : s) ?? "de";
  }

  #geladen({ doc, index }: { doc: Document; index: number }): void {
    setzeStil(doc, epubCss(this.darstellung, this.#schriften), this.#sprache());
    const rahmen = doc.defaultView?.frameElement as HTMLElement | null;
    if (rahmen) rahmen.style.backgroundColor = randfarbe(this.darstellung);
    requestAnimationFrame(() => void this.zeichne(this.#markierungen));
    const auswerten = () => this.#auswahl(doc, index);
    doc.addEventListener("pointerup", () => setTimeout(auswerten));
    doc.addEventListener("selectionchange", () => {
      clearTimeout(this.#uhr);
      this.#uhr = setTimeout(auswerten, RUHE_AUSWAHL_MS);
    });
    doc.addEventListener("keydown", (e) => this.griffe.beiTaste(e));
  }

  #auswahl(doc: Document, index: number): void {
    const wahl = doc.getSelection();
    const text = wahl?.toString().trim() ?? "";
    if (!wahl || !wahl.rangeCount || text.length < 2) {
      this.griffe.beiAuswahl(null);
      return;
    }
    const bereich = wahl.getRangeAt(0);
    const b = bereich.getBoundingClientRect();
    const r = (doc.defaultView?.frameElement as HTMLElement | null)?.getBoundingClientRect() ?? { left: 0, top: 0 };
    this.griffe.beiAuswahl({ text, cfi: this.#view?.getCFI(index, bereich) ?? "", x: r.left + b.left + b.width / 2, oben: r.top + b.top, unten: r.top + b.bottom });
  }

  waehleAb(): void {
    for (const { doc } of this.#view?.renderer?.getContents() ?? []) doc.getSelection()?.removeAllRanges();
  }

  #gerueckt(s: FoliateStand): void {
    const nr = this.kapitel.findIndex((k) => k.ziel === s.tocItem?.href);
    this.griffe.beiStand({ anteil: s.fraction ?? 0, cfi: s.cfi ?? "", kapitel: s.tocItem?.label?.trim() ?? "", kapitelNr: nr, gedruckt: s.pageItem?.label?.trim() ?? "" });
  }

  // Einseitig heißt eine Spalte, auch wenn zwei nebeneinander passten
  #seitenmass(): void {
    const r = this.#view?.renderer;
    if (!r) return;
    const d = this.darstellung;
    r.setAttribute("margin", RAND);
    r.setAttribute("max-column-count", d.einseitig ? "1" : "2");
    r.setAttribute("max-inline-size", `${d.einseitig ? breite(d) : Math.round(breite(d) / 2)}px`);
  }

  stile(d: Epubdarstellung): void {
    this.darstellung = d;
    const r = this.#view?.renderer;
    if (!this.#view || !r) return;
    const css = epubCss(d, this.#schriften);
    for (const { doc } of r.getContents()) {
      setzeStil(doc, css, this.#sprache());
      const rahmen = doc.defaultView?.frameElement as HTMLElement | null;
      if (rahmen) rahmen.style.backgroundColor = randfarbe(d);
    }
    // Die Bibliothek malt die Seitenränder mit dem beim Laden gemerkten Grund; setStyles lässt sie ihn neu nehmen
    r.setStyles?.("");
  }

  mass(d: Epubdarstellung): void {
    this.darstellung = d;
    this.#seitenmass();
  }

  vor = () => this.#view?.next();
  zurueck = () => this.#view?.prev();

  async zuAnteil(anteil: number): Promise<void> {
    await this.#view?.goToFraction(Math.min(0.9999, Math.max(0, anteil)));
  }

  async springe(ziel: string): Promise<void> {
    await this.#view?.goTo(ziel);
  }

  /** Stelle einer Markierung: die Bibliothek landet manchmal eine Seite zu früh, darum zweimal */
  async zurStelle(cfi: string): Promise<void> {
    await this.#view?.goTo(cfi);
    setTimeout(() => void this.#view?.goTo(cfi), 150);
  }

  async zeichne(markierungen: Markierung[]): Promise<void> {
    const view = this.#view;
    if (!view) return;
    const bleibt = new Set(markierungen.map((m) => m.cfi_range));
    const weg = this.#markierungen.filter((m) => !bleibt.has(m.cfi_range));
    this.#markierungen = markierungen;
    // Stellen anderer Kapitel sind gerade nicht geladen, das ist kein Fehler
    for (const m of weg) await view.deleteAnnotation({ value: m.cfi_range }).catch(() => {});
    for (const m of markierungen) if (m.cfi_range.startsWith("epubcfi")) await view.addAnnotation({ value: m.cfi_range, color: m.color }).catch(() => {});
  }

  kapiteltext(): string {
    return (this.#view?.renderer?.getContents() ?? []).map((c) => c.doc.body?.textContent ?? "").join("\n").trim();
  }

  /** Alle Treffer im Buch; liefert die Nummer des ersten ab dem Anteil */
  async suche(wort: string, ab: number): Promise<number> {
    const view = this.#view;
    this.treffer = [];
    if (!view) return -1;
    for await (const r of view.search({ query: wort })) {
      if (r === "done" || typeof r === "string") break;
      if (r.subitems) this.treffer.push(...r.subitems.map((s) => s.cfi));
      else if (r.cfi) this.treffer.push(r.cfi);
    }
    if (!this.treffer.length) return -1;
    const grenzen = view.getSectionFractions();
    const teil = ab > 0 ? Math.max(0, grenzen.findLastIndex((g) => g <= ab)) : 0;
    const nr = this.treffer.findIndex((cfi) => view.resolveCFI(cfi).index >= teil);
    return nr >= 0 ? nr : 0;
  }

  sucheBeenden(): void {
    this.#view?.clearSearch();
    this.treffer = [];
  }
}
