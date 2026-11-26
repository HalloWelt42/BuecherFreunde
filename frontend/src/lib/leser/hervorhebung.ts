// Hervorheben, ohne den Satz anzurühren: kein Element im Text, keine Breite, kein Abstand. Gemalt wird mit der
// Hervorhebungs-Schnittstelle des Browsers (CSS Custom Highlight API); wo es sie nicht gibt, mit Rechtecken hinter dem Text.

export interface Hervorhebungsart {
  /** Eindeutig je Dokument, nur Buchstaben, Ziffern und Bindestrich */
  name: string;
  farbe: string;
  /** Wer höher steht, malt darüber (Vorlesesatz über Markierung) */
  rang: number;
}

type Fenster = Window & typeof globalThis & { Highlight?: typeof Highlight };

const ARTEN = new WeakMap<Document, Map<string, string>>();

/** Regel für eine Art einmal je Dokument */
function regel(dok: Document, art: Hervorhebungsart): void {
  const da = ARTEN.get(dok) ?? new Map<string, string>();
  ARTEN.set(dok, da);
  if (da.get(art.name) === art.farbe) return;
  da.set(art.name, art.farbe);
  let stil = dok.getElementById("bf-hervorhebung") as HTMLStyleElement | null;
  if (!stil) {
    stil = dok.createElement("style");
    stil.id = "bf-hervorhebung";
    (dok.head ?? dok.documentElement).append(stil);
  }
  stil.textContent = [...da].map(([n, f]) => `::highlight(${n}) { background-color: ${f}; color: inherit; }`).join("\n");
}

export const kannHervorheben = (dok: Document = document): boolean => {
  const f = dok.defaultView as Fenster | null;
  return !!f?.CSS?.highlights && typeof f.Highlight === "function";
};

/** Hebt Bereiche einer Art hervor; leer nimmt sie weg. Liefert die gesetzte Hervorhebung (nur mit der Schnittstelle). */
export function hebeHervor(dok: Document, art: Hervorhebungsart, bereiche: Range[], ersatz?: Rechteckschicht): Highlight | null {
  if (!kannHervorheben(dok)) {
    ersatz?.setze(art, bereiche);
    return null;
  }
  const f = dok.defaultView as Fenster;
  if (!bereiche.length) {
    f.CSS.highlights.delete(art.name);
    return null;
  }
  regel(dok, art);
  const h = new f.Highlight!(...bereiche);
  h.priority = art.rang;
  f.CSS.highlights.set(art.name, h);
  return h;
}

/** Ersatz: Rechtecke in einer eigenen Schicht hinter dem Text; nach jeder Bewegung des Satzes neu zu zeichnen */
export class Rechteckschicht {
  #schicht: HTMLElement;
  #arten = new Map<string, { art: Hervorhebungsart; bereiche: Range[] }>();

  constructor(private traeger: HTMLElement) {
    this.#schicht = traeger.ownerDocument.createElement("div");
    this.#schicht.className = "hervorhebungen";
    this.#schicht.setAttribute("aria-hidden", "true");
    traeger.prepend(this.#schicht);
  }

  setze(art: Hervorhebungsart, bereiche: Range[]): void {
    if (bereiche.length) this.#arten.set(art.name, { art, bereiche });
    else this.#arten.delete(art.name);
    this.zeichne();
  }

  zeichne(): void {
    const t = this.traeger.getBoundingClientRect();
    const stuecke: HTMLElement[] = [];
    for (const { art, bereiche } of [...this.#arten.values()].sort((a, b) => a.art.rang - b.art.rang)) {
      for (const b of bereiche) {
        for (const r of b.getClientRects()) {
          if (!r.width || r.right < t.left || r.left > t.right) continue;
          const s = this.traeger.ownerDocument.createElement("i");
          Object.assign(s.style, { left: `${r.left - t.left}px`, top: `${r.top - t.top}px`, width: `${r.width}px`, height: `${r.height}px`, background: art.farbe });
          stuecke.push(s);
        }
      }
    }
    this.#schicht.replaceChildren(...stuecke);
  }

  zerstoere(): void {
    this.#schicht.remove();
  }
}
