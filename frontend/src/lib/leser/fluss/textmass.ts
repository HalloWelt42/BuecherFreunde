// Stellen im Text, unabhängig davon, wie er gerade umbrochen ist: ein Zeichen in einem Textknoten oder eine Abbildung.
// Anteile zählen Zeichen, nicht Bildpunkte; so bleibt eine Stelle beim Drehen und bei anderer Schrift dieselbe.
export interface Anker {
  knoten: Node;
  versatz: number;
}

/** Lage im Satz; der Ursprung ist Sache dessen, der misst */
export interface Rechteck {
  links: number;
  oben: number;
  rechts: number;
  unten: number;
}

export type Messer = (a: Anker) => Rechteck | null;

interface Stueck {
  knoten: Node;
  /** Zeichen vor diesem Stück */
  ab: number;
  laenge: number;
}

const ABBILDUNGEN = new Set(["IMG", "SVG", "CANVAS", "VIDEO"]);
const OHNE_TEXT = "button, style, script, [hidden]";

export class Textmass {
  #stuecke: Stueck[] | null = null;
  #nach = new Map<Node, Stueck>();
  #beobachter: MutationObserver | null = null;

  constructor(private wurzel: HTMLElement, private messe: Messer) {
    this.#beobachter = new MutationObserver(() => this.veraltet());
    this.#beobachter.observe(wurzel, { childList: true, subtree: true, characterData: true });
  }

  zerstoere(): void {
    this.#beobachter?.disconnect();
  }

  veraltet(): void {
    this.#stuecke = null;
  }

  #liste(): Stueck[] {
    // Noch nicht gemeldete Änderungen zählen mit: ein Umbau, nach dem sofort gemessen wird
    if (this.#beobachter?.takeRecords().length) this.#stuecke = null;
    if (this.#stuecke) return this.#stuecke;
    const aus: Stueck[] = [];
    let ab = 0;
    const geher = document.createTreeWalker(this.wurzel, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let k = geher.nextNode(); k; k = geher.nextNode()) {
      if (k.nodeType === Node.ELEMENT_NODE) {
        if (!ABBILDUNGEN.has(k.nodeName.toUpperCase())) continue;
      } else if (!(k as Text).data.trim() || k.parentElement?.closest(OHNE_TEXT)) continue;
      const laenge = k.nodeType === Node.ELEMENT_NODE ? 1 : (k as Text).data.length;
      aus.push({ knoten: k, ab, laenge });
      ab += laenge;
    }
    this.#nach = new Map(aus.map((s) => [s.knoten, s]));
    return (this.#stuecke = aus);
  }

  get laenge(): number {
    const l = this.#liste().at(-1);
    return l ? l.ab + l.laenge : 0;
  }

  /** Anteil der Stelle am ganzen Text, 0 bis 1 */
  anteil(a: Anker): number {
    const alle = this.laenge;
    if (!alle) return 0;
    return Math.min(1, this.#zeichen(a) / alle);
  }

  #zeichen(a: Anker): number {
    const liste = this.#liste();
    const genau = this.#nach.get(a.knoten);
    if (genau) return genau.ab + Math.min(a.versatz, genau.laenge);
    // Die Stelle liegt an einem Element oder in einem Knoten ohne Text: das nächste Stück danach zählt
    const naechstes = liste.find((s) => (a.knoten.compareDocumentPosition(s.knoten) & (Node.DOCUMENT_POSITION_FOLLOWING | Node.DOCUMENT_POSITION_CONTAINED_BY)) > 0);
    return naechstes ? naechstes.ab : this.laenge;
  }

  /** Stelle bei diesem Anteil des Textes */
  beiAnteil(anteil: number): Anker | null {
    const liste = this.#liste();
    if (!liste.length) return null;
    const zeichen = Math.max(0, Math.min(this.laenge - 1, Math.round(anteil * this.laenge)));
    let [von, bis] = [0, liste.length - 1];
    while (von < bis) {
      const mitte = (von + bis + 1) >> 1;
      if (liste[mitte].ab <= zeichen) von = mitte;
      else bis = mitte - 1;
    }
    return { knoten: liste[von].knoten, versatz: Math.min(liste[von].laenge - 1, zeichen - liste[von].ab) };
  }

  /** Erste Stelle in einem Element; null ohne Text und Abbildung */
  anfangVon(e: Node): Anker | null {
    const s = this.#liste().find((x) => x.knoten === e || e.contains(x.knoten));
    return s ? { knoten: s.knoten, versatz: 0 } : null;
  }

  /** Lage der Stelle; trägt ihr Zeichen keine (umbrochener Leerraum), gilt das nächste daneben */
  lage(a: Anker): Rechteck | null {
    this.#liste();
    const laenge = this.#nach.get(a.knoten)?.laenge ?? (a.knoten as Text).length ?? 1;
    const start = Math.max(0, Math.min(a.versatz, laenge - 1));
    return this.#abZeichen(a.knoten, start, laenge - 1)?.r ?? this.#rueckwaerts(a.knoten, start);
  }

  #abZeichen(knoten: Node, von: number, bis: number): { r: Rechteck; versatz: number } | null {
    for (let v = von; v <= bis; v++) {
      const r = this.messe({ knoten, versatz: v });
      if (r) return { r, versatz: v };
    }
    return null;
  }

  #rueckwaerts(knoten: Node, von: number): Rechteck | null {
    for (let v = von - 1; v >= 0; v--) {
      const r = this.messe({ knoten, versatz: v });
      if (r) return r;
    }
    return null;
  }

  /** Erste Stelle, die nicht mehr vor der Grenze liegt. Der Text läuft in Lesefolge, darum genügt Halbieren. */
  erste(vorher: (r: Rechteck) => boolean): Anker | null {
    const liste = this.#liste();
    let [von, bis] = [0, liste.length];
    while (von < bis) {
      const mitte = (von + bis) >> 1;
      let m = mitte;
      let r: Rechteck | null = null;
      while (m < bis && !(r = this.#ende(liste[m]))) m++;
      if (!r) bis = mitte;
      else if (vorher(r)) von = m + 1;
      else bis = m;
    }
    const s = liste[von];
    if (!s) return null;
    let [a, b] = [0, s.laenge - 1];
    while (a < b) {
      const mitte = (a + b) >> 1;
      const z = this.#abZeichen(s.knoten, mitte, b);
      if (!z) b = mitte;
      else if (vorher(z.r)) a = z.versatz + 1;
      else b = mitte;
    }
    return { knoten: s.knoten, versatz: Math.min(a, s.laenge - 1) };
  }

  #ende(s: Stueck): Rechteck | null {
    return this.messe({ knoten: s.knoten, versatz: s.laenge - 1 }) ?? this.#rueckwaerts(s.knoten, s.laenge - 1);
  }
}

/** Lage eines Zeichens oder einer Abbildung im Fenster */
export function messeImFenster(a: Anker): DOMRect | null {
  if (a.knoten.nodeType === Node.ELEMENT_NODE) {
    const r = (a.knoten as Element).getBoundingClientRect();
    return r.width > 0 || r.height > 0 ? r : null;
  }
  const text = a.knoten as Text;
  if (!text.length || !text.isConnected) return null;
  const bereich = document.createRange();
  const v = Math.max(0, Math.min(a.versatz, text.length - 1));
  bereich.setStart(text, v);
  bereich.setEnd(text, v + 1);
  for (const r of bereich.getClientRects()) if (r.width > 0 && r.height > 0) return r;
  return null;
}
