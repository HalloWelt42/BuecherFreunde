// Markierungen und Fundstelle auf der Textebene der PDF-Seiten, zeichengenau: über ihren Wortlaut im Text der Seite
// gefunden und mit Hervorhebungen gemalt wie im Text (lib/leser/hervorhebung.ts). Die Stücke der Textebene von pdf.js
// sind ganze Zeilen und Läufe; gefärbt wird darum nie ein Stück, nur der Bereich der gewählten Zeichen (BF-38). Die
// Textebene selbst bleibt unberührt.
//
// Jede Seite meldet sich, wenn pdf.js sie samt Textebene fertig hat. Mit der Schnittstelle des Browsers malt eine Art
// (Farbe) alle ihre Bereiche auf allen gezeichneten Seiten zusammen; ohne sie trägt jede Seite eine eigene Schicht mit
// Rechtecken, die mit der Seite gezeichnet wird.
import type { Markierung } from "../../typen";
import { VORGABE_STIFT } from "../farben";
import { hebeHervor, kannHervorheben, Rechteckschicht, type Hervorhebungsart } from "../hervorhebung";
import { bereichAus, stiftart, textknoten, TREFFER } from "../text/markierung";
import { findeZeichen } from "../textsuche";

interface Seitenstand {
  ebene: HTMLElement;
  markiert: Map<number, { bereich: Range; art: Hervorhebungsart }>;
  fund: Range | null;
  schicht?: Rechteckschicht;
}

export class Pdfmarkierungen {
  #seiten = new Map<number, Seitenstand>();
  /** Was diese Seiten gerade malen, je Name der Art */
  #gemalt = new Map<string, { art: Hervorhebungsart; h: Highlight | null }>();

  constructor(private dok: Document = document) {}

  /** Eine Seite ist samt Textebene gezeichnet: ihre Markierungen und, nur hier, die Fundstelle suchen. Liefert die Fundstelle. */
  beschrifte(nr: number, ebene: HTMLElement, markierungen: readonly Markierung[], fundstelle = ""): Range | null {
    const knoten = textknoten(ebene);
    const finde = (wortlaut: string) => {
      const ort = findeZeichen(knoten, wortlaut, null);
      return ort && bereichAus(ort.von, ort.bis);
    };
    const markiert: Seitenstand["markiert"] = new Map();
    for (const m of markierungen) {
      if (m.cfi_range !== `page:${nr}`) continue;
      const bereich = finde(m.text_snippet ?? "");
      if (bereich) markiert.set(m.id, { bereich, art: stiftart(m.color || VORGABE_STIFT) });
    }
    const fund = fundstelle ? finde(fundstelle.replace(/^"|"$/g, "")) : null;
    this.#seiten.get(nr)?.schicht?.zerstoere();
    const stand: Seitenstand = { ebene, markiert, fund };
    this.#seiten.set(nr, stand);
    if (kannHervorheben(this.dok)) this.#maleAlle();
    else this.#maleSeite(stand);
    return fund;
  }

  /** Bereich einer Markierung auf einer gezeichneten Seite (Marken am Rand) */
  bereich(id: number): Range | null {
    for (const s of this.#seiten.values()) {
      const m = s.markiert.get(id);
      if (m && s.ebene.isConnected) return m.bereich;
    }
    return null;
  }

  /** Nimmt alles weg, was diese Seiten gemalt haben; was eine andere Ansicht inzwischen malt, bleibt */
  leere(): void {
    const f = this.dok.defaultView as (Window & typeof globalThis) | null;
    for (const { h } of this.#gemalt.values()) {
      for (const [name, jetzt] of f?.CSS?.highlights ?? []) if (h && jetzt === h) f!.CSS.highlights.delete(name);
    }
    this.#gemalt.clear();
    for (const s of this.#seiten.values()) s.schicht?.zerstoere();
    this.#seiten.clear();
  }

  // Seiten, die pdf.js weggeräumt hat, zählen nicht mehr
  #lebende(): Seitenstand[] {
    for (const [nr, s] of this.#seiten) if (!s.ebene.isConnected) this.#seiten.delete(nr);
    return [...this.#seiten.values()];
  }

  #maleAlle(): void {
    const je = new Map<string, { art: Hervorhebungsart; bereiche: Range[] }>();
    const dazu = (art: Hervorhebungsart, bereich: Range) => {
      const g = je.get(art.name) ?? { art, bereiche: [] };
      g.bereiche.push(bereich);
      je.set(art.name, g);
    };
    for (const s of this.#lebende()) {
      for (const { bereich, art } of s.markiert.values()) dazu(art, bereich);
      if (s.fund) dazu(TREFFER, s.fund);
    }
    for (const [name, { art }] of this.#gemalt) if (!je.has(name)) hebeHervor(this.dok, art, []);
    this.#gemalt.clear();
    for (const [name, { art, bereiche }] of je) this.#gemalt.set(name, { art, h: hebeHervor(this.dok, art, bereiche) });
  }

  #maleSeite(s: Seitenstand): void {
    const traeger = s.ebene.parentElement;
    if (!traeger) return;
    s.schicht = new Rechteckschicht(traeger);
    const je = new Map<string, { art: Hervorhebungsart; bereiche: Range[] }>();
    for (const { bereich, art } of s.markiert.values()) je.set(art.name, { art, bereiche: [...(je.get(art.name)?.bereiche ?? []), bereich] });
    if (s.fund) je.set(TREFFER.name, { art: TREFFER, bereiche: [s.fund] });
    for (const { art, bereiche } of je.values()) s.schicht.setze(art, bereiche);
  }
}
