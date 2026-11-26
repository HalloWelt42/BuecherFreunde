// Hülle um die EPUB-Bibliothek: öffnen, blättern, springen, Stile, Markierungen, Suche, Auswahl
import type { FoliateKapitel, FoliateStand, View } from "foliate-js/view.js";
import { anfrage } from "../../api/client";
import { beobachteDokument } from "../../flucht";
import { beobachteKontext } from "../../stand/kontextmenue.svelte";
import type { Markierung } from "../../typen";
import { blaettergesten, type Blaettergriffe } from "../blaettergesten";
import { VORGABE_STIFT } from "../farben";
import type { Leseart } from "../fluss/fluss";
import type { Kapitel } from "../typen";
import { kapitelrand } from "./kapitelrand";
import { nutzeSchrift, schriftCss } from "../schriften";
import { einspaltig, epubCss, randfarbe, setzeStil, type Epubdarstellung } from "./stile";

export interface Epubstand {
  anteil: number;
  cfi: string;
  kapitel: string;
  kapitelNr: number;
  /** Seite der gedruckten Ausgabe, wenn das Buch ein Seitenverzeichnis hat */
  gedruckt: string;
}

/** Was den Umbruch bestimmt und nicht zum Buch, sondern zum Gerät gehört */
export interface Seitenmass {
  art: Leseart;
  /** Rand links und rechts, und oben und unten */
  rand: number;
  oben: number;
  /** Breite einer Spalte (Breite des Blatts) */
  spalte: number;
}

export interface Epubgriffe {
  beiStand(stand: Epubstand): void;
  beiAuswahl(a: { text: string; cfi: string; x: number; oben: number; unten: number } | null): void;
  beiTaste(e: KeyboardEvent): void;
  /** Tippen in die Mitte, und was vor dem Tippen kommt */
  mitte(): void;
  belegt(punkt: { x: number; y: number }): boolean;
  /** Ein Abschnitt ist geladen */
  geladen(doc: Document): void;
  gerollt(): void;
  /** Die Maus bewegt sich über dem Kapitel */
  maus(e: PointerEvent): void;
}

const RUHE_AUSWAHL_MS = 350;
/** So weit rückt ein Pfeil hoch oder runter beim Scrollen */
const ZEILEN_PX = 80;

function flach(toc: FoliateKapitel[], tiefe = 0): Kapitel[] {
  return toc.flatMap((k) => [{ titel: k.label?.trim() || "Ohne Titel", tiefe, ziel: k.href }, ...flach(k.subitems ?? [], tiefe + 1)]);
}

export class EpubAnzeige {
  kapitel: Kapitel[] = [];
  treffer: string[] = [];
  #view: View | null = null;
  /** Regeln der Lesehilfen, an jedes Kapitel gehängt */
  #zusatz = "";
  #overlayer: { highlight: unknown } | null = null;
  #markierungen: Markierung[] = [];
  #uhr: ReturnType<typeof setTimeout> | undefined;

  #gesten: () => void;
  // Der Rand hängt an der Breite der Fläche (Drehen, Vollbild)
  #groesse = new ResizeObserver(() => this.#neueGroesse());
  /** Stelle, an der zuletzt in Ruhe gelesen wurde; nach einem neuen Umbruch kehrt die Ansicht dorthin zurück */
  #ruhestelle = "";
  #breite = 0;
  /** Läuft, solange ein Umbruch nach neuer Breite auf die Rückkehr wartet */
  #umbruch: ReturnType<typeof setTimeout> | undefined;

  constructor(private flaeche: HTMLElement, private darstellung: Epubdarstellung, private seite: Seitenmass, private griffe: Epubgriffe) {
    this.#gesten = this.#hoere(flaeche);
    this.#groesse.observe(flaeche);
  }

  /** adresse: die Datei, das Original oder eine Übersetzung (BF-71) */
  async oeffne(adresse: string, cfi: string): Promise<void> {
    const [{ View }, { Overlayer }, antwort] = await Promise.all([import("foliate-js/view.js"), import("foliate-js/overlayer.js"), anfrage(adresse)]);
    const datei = new File([await antwort.blob()], "buch.epub", { type: "application/epub+zip" });
    const view = new View();
    this.#view = view;
    this.#overlayer = Overlayer;
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
    // Gescrollt meldet die Bibliothek die Stelle erst nach einer Ruhe; was am Text hängt, soll gleich mitgehen
    view.renderer?.addEventListener("scroll", () => this.griffe.gerollt());
    this.stile(this.darstellung);
  }

  schliesse(): void {
    clearTimeout(this.#uhr);
    clearTimeout(this.#umbruch);
    this.#gesten();
    this.#groesse.disconnect();
    this.#view?.close();
    this.#view?.remove();
    this.#view = null;
  }

  #sprache(): string {
    const s = this.#view?.book?.metadata?.language;
    return (Array.isArray(s) ? s[0] : s) ?? "de";
  }

  #geladen({ doc, index }: { doc: Document; index: number }): void {
    setzeStil(doc, epubCss(this.darstellung, schriftCss(this.darstellung.schrift)) + this.#zusatz, this.#sprache());
    const rahmen = doc.defaultView?.frameElement as HTMLElement | null;
    if (rahmen) rahmen.style.backgroundColor = randfarbe(this.darstellung);
    requestAnimationFrame(() => void this.zeichne(this.#markierungen));
    // Ein Druck in den Text schließt offene Felder wie überall (BF-39)
    beobachteDokument(doc);
    // Rechtsklick im Text: das eigene Menü des Lesers, wie außerhalb des Rahmens (BF-42)
    beobachteKontext(doc, () => this.flaeche);
    const auswerten = () => this.#auswahl(doc, index);
    doc.addEventListener("pointerup", () => setTimeout(auswerten));
    doc.addEventListener("selectionchange", () => {
      clearTimeout(this.#uhr);
      this.#uhr = setTimeout(auswerten, RUHE_AUSWAHL_MS);
    });
    doc.addEventListener("keydown", (e) => this.griffe.beiTaste(e));
    doc.addEventListener("pointermove", (e) => this.griffe.maus(e));
    this.#hoere(doc);
    this.griffe.geladen(doc);
  }

  /** Anteil im Buch, an dem ein Abschnitt beginnt, für eine Stelle */
  anteilVon(cfi: string): number | null {
    try {
      const index = this.#view?.resolveCFI(cfi).index;
      return index === undefined ? null : (this.#view?.getSectionFractions()[index] ?? null);
    } catch {
      return null;
    }
  }

  /** Höhe einer Stelle im Fenster, wenn sie auf der offenen Seite steht */
  lageVon(cfi: string): number | null {
    const g = this.#view?.renderer?.getContents()[0];
    try {
      const z = this.#view?.resolveCFI(cfi) as { index: number; anchor?: (d: Document) => Range } | undefined;
      if (!g || !z || z.index !== g.index) return null;
      const r = z.anchor?.(g.doc);
      const rahmen = g.doc.defaultView?.frameElement?.getBoundingClientRect();
      const f = this.flaeche.getBoundingClientRect();
      // Eine Stelle ohne Ausdehnung (nur ein Element) hat keine Zeilen: dann gilt das Element
      const zeilen = [...(r?.getClientRects() ?? [])];
      const element = r?.startContainer.nodeType === Node.ELEMENT_NODE ? (r.startContainer as Element).children[r.startOffset] ?? (r.startContainer as Element) : r?.startContainer.parentElement;
      if (!zeilen.length && element) zeilen.push(element.getBoundingClientRect());
      for (const q of zeilen) {
        const [x, y] = [q.left + (rahmen?.left ?? 0), q.top + (rahmen?.top ?? 0)];
        if (q.width && x < f.right && x + q.width > f.left && y + q.height > f.top && y < f.bottom) return y;
      }
    } catch {
      // Stelle eines anderen Buchs oder kaputt
    }
    return null;
  }

  /** Lesehilfen im Kapitel: Abstände, Abbildungen, Ruhe */
  zusatz(css: string): void {
    if (css === this.#zusatz) return;
    this.#zusatz = `\n${css}`;
    this.stile(this.darstellung);
  }

  /** Die Dokumente der gezeigten Kapitel mit der Lage ihres Rahmens im Fenster (Codestellen, BF-29) */
  dokumente(): { doc: Document; x: number; y: number }[] {
    const inhalte = (this.#view?.renderer?.getContents() ?? []) as { doc: Document }[];
    return inhalte.map(({ doc }) => {
      const r = (doc.defaultView?.frameElement as HTMLElement | null)?.getBoundingClientRect();
      return { doc, x: r?.left ?? 0, y: r?.top ?? 0 };
    });
  }

  get ansicht(): View | null {
    return this.#view;
  }

  /** Hebt einen Bereich im gezeigten Abschnitt mit den Mitteln der Bibliothek hervor (wo der Browser es selbst nicht kann) */
  male(bereich: Range | null, farbe: string): void {
    const inhalt = this.#view?.renderer?.getContents()[0] as { overlayer?: { add(k: string, r: Range, f: unknown, o: object): void; remove(k: string): void } } | undefined;
    inhalt?.overlayer?.remove("bf-vorlesen");
    if (bereich && this.#overlayer) inhalt?.overlayer?.add("bf-vorlesen", bereich, this.#overlayer.highlight, { color: farbe });
  }

  // Finger, Rad und Maus: auf der Fläche und in jedem Kapitelrahmen gleich
  #hoere(ort: HTMLElement | Document): () => void {
    const rahmen = () => ("defaultView" in ort ? ort.defaultView?.frameElement?.getBoundingClientRect() : undefined);
    const versatz = () => rahmen()?.left ?? 0;
    const versatzOben = () => rahmen()?.top ?? 0;
    const griffe: Blaettergriffe = { gilt: () => this.seite.art === "blaettern", vor: this.vor, zurueck: this.zurueck, mitte: () => this.griffe.mitte(), belegt: (p) => this.griffe.belegt(p) };
    const blaettern = blaettergesten(ort, { rahmen: () => this.flaeche.getBoundingClientRect(), versatz, versatzOben }, griffe);
    const rand = kapitelrand(ort, { gilt: () => this.seite.art === "scrollen", amRand: (r) => this.#amRand(r), weiter: (r) => void (r > 0 ? this.vor() : this.zurueck()) });
    return () => {
      blaettern();
      rand();
    };
  }

  #amRand(richtung: 1 | -1): boolean {
    const r = this.#view?.renderer;
    return richtung > 0 ? (r?.viewSize ?? 0) - (r?.end ?? 0) <= 2 : (r?.start ?? 0) <= 1;
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

  // Neue Breite (Feld daneben, Breite des Blatts, Fenster, Drehen): die Bibliothek bricht neu um und landet dabei oft eine
  // Spalte weiter; die gelesene Stelle soll auf dem Schirm bleiben (BF-41)
  #neueGroesse(): void {
    this.#seitenmass();
    const breite = this.flaeche.clientWidth;
    if (!breite || breite === this.#breite) return;
    const zuvor = this.#breite;
    this.#breite = breite;
    const ziel = this.#ruhestelle;
    if (!zuvor || !ziel) return;
    clearTimeout(this.#umbruch);
    this.#umbruch = setTimeout(() => {
      void this.zurStelle(ziel);
      this.#umbruch = setTimeout(() => (this.#umbruch = undefined), 400);
    }, 250);
  }

  #gerueckt(s: FoliateStand): void {
    const nr = this.kapitel.findIndex((k) => k.ziel === s.tocItem?.href);
    // Gescrollt zählt die Bibliothek nur, was über dem Bild liegt: am Ende des Buchs fehlte sonst der letzte Schirm
    const r = this.#view?.renderer;
    const zuEnde = !!r?.scrolled && !!r.atEnd && this.#amRand(1);
    // Meldet die Bibliothek eine Stelle, weil sie nach neuer Breite schon umgebrochen hat, zählt sie nicht als gelesen
    if (!this.#umbruch && this.flaeche.clientWidth === this.#breite) this.#ruhestelle = s.cfi ?? "";
    this.griffe.beiStand({ anteil: zuEnde ? 1 : (s.fraction ?? 0), cfi: s.cfi ?? "", kapitel: s.tocItem?.label?.trim() ?? "", kapitelNr: nr, gedruckt: s.pageItem?.label?.trim() ?? "" });
  }

  // Einseitig heißt eine Spalte, auch wenn zwei nebeneinander passten
  #seitenmass(): void {
    const r = this.#view?.renderer;
    if (!r) return;
    const d = this.darstellung;
    const { art, rand, oben, spalte } = this.seite;
    const [eins, scrollt, weite] = [einspaltig(d, art), art === "scrollen", this.flaeche.clientWidth || 1];
    const werte = {
      margin: `${oben}px`,
      // Die Bibliothek nimmt den Rand als Anteil der Breite, gescrollt der Breite ohne ihn
      gap: `${((rand / (scrollt ? weite + rand : weite)) * 100).toFixed(3)}%`,
      flow: scrollt ? "scrolled" : "paginated", "max-column-count": eins ? "1" : "2", "max-inline-size": `${spalte}px`,
    };
    // Jedes Setzen bricht das Kapitel neu um, darum nur, was sich ändert
    for (const [name, wert] of Object.entries(werte)) if (r.getAttribute(name) !== wert) r.setAttribute(name, wert);
  }

  stile(d: Epubdarstellung): void {
    this.darstellung = d;
    const r = this.#view?.renderer;
    if (!this.#view || !r) return;
    const css = epubCss(d, schriftCss(d.schrift)) + this.#zusatz;
    // Auch die Seite selbst kennt die Schrift, für die Probe im Feld
    if (d.schrift) nutzeSchrift(d.schrift);
    for (const { doc } of r.getContents()) {
      setzeStil(doc, css, this.#sprache());
      const rahmen = doc.defaultView?.frameElement as HTMLElement | null;
      if (rahmen) rahmen.style.backgroundColor = randfarbe(d);
    }
    // Die Bibliothek malt die Seitenränder mit dem beim Laden gemerkten Grund; setStyles lässt sie ihn neu nehmen
    r.setStyles?.("");
  }

  mass(d: Epubdarstellung, seite: Seitenmass): void {
    this.darstellung = d;
    this.seite = seite;
    this.#seitenmass();
  }

  vor = (): void => void this.#view?.next();
  zurueck = (): void => void this.#view?.prev();
  zeileVor = (): void => void this.#view?.next(ZEILEN_PX);
  zeileZurueck = (): void => void this.#view?.prev(ZEILEN_PX);

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
