// Der Text einiger Elemente als eine Zeichenkette, mit dem Weg zurück zu den Textknoten. Blöcke trennt eine Leerzeile, so
// enden Sätze an Absätzen. Was nicht vorgelesen wird (Code, Tasten, Seitenmarken), zählt nicht mit.
const AUSSER = "pre, button, style, script, svg, .seitenmarke, .hervorhebungen, [hidden], [aria-hidden='true']";
const BLOCK = /^(P|LI|H[1-6]|BLOCKQUOTE|TD|TH|DT|DD|FIGCAPTION|CAPTION|SECTION|ASIDE|ARTICLE|DIV|HEADER|FOOTER|TR|PRE)$/;

interface Stueck {
  knoten: Text;
  ab: number;
}

function blockVon(k: Node, grenze: Element): Element | null {
  for (let e = k.parentElement; e && e !== grenze; e = e.parentElement) if (BLOCK.test(e.tagName.toUpperCase())) return e;
  return grenze;
}

export class Textkarte {
  text = "";
  #stuecke: Stueck[] = [];

  constructor(wurzeln: Element[]) {
    const teile: string[] = [];
    let laenge = 0;
    let block: Element | null = null;
    for (const w of wurzeln) {
      const geher = w.ownerDocument.createTreeWalker(w, NodeFilter.SHOW_TEXT, { acceptNode: (k) => (k.parentElement?.closest(AUSSER) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
      for (let k = geher.nextNode() as Text | null; k; k = geher.nextNode() as Text | null) {
        const b = blockVon(k, w);
        if (block && b !== block && laenge) {
          teile.push("\n\n");
          laenge += 2;
        }
        block = b;
        this.#stuecke.push({ knoten: k, ab: laenge });
        teile.push(k.data);
        laenge += k.data.length;
      }
    }
    this.text = teile.join("");
  }

  /** Stehen noch alle Knoten im Dokument? */
  get gueltig(): boolean {
    return this.#stuecke.every((s) => s.knoten.isConnected);
  }

  /** Knoten und Versatz zu einem Zeichen; zwischen zwei Blöcken gilt der Anfang des nächsten */
  stelle(zeichen: number): { knoten: Text; versatz: number } | null {
    const liste = this.#stuecke;
    if (!liste.length) return null;
    let [von, bis] = [0, liste.length - 1];
    while (von < bis) {
      const mitte = (von + bis + 1) >> 1;
      if (liste[mitte].ab <= zeichen) von = mitte;
      else bis = mitte - 1;
    }
    const s = liste[von];
    const versatz = zeichen - s.ab;
    if (versatz <= s.knoten.length) return { knoten: s.knoten, versatz: Math.max(0, versatz) };
    const naechstes = liste[von + 1];
    return naechstes ? { knoten: naechstes.knoten, versatz: 0 } : { knoten: s.knoten, versatz: s.knoten.length };
  }

  bereich(von: number, bis: number): Range | null {
    const a = this.stelle(von);
    const b = this.stelle(Math.max(von, bis));
    if (!a || !b) return null;
    const r = a.knoten.ownerDocument.createRange();
    r.setStart(a.knoten, a.versatz);
    r.setEnd(b.knoten, b.versatz);
    return r;
  }

  /** Zeichen zu einer Stelle im Dokument; liegt sie außerhalb, das nächste danach */
  zeichenVon(knoten: Node, versatz: number): number {
    const genau = this.#stuecke.find((s) => s.knoten === knoten);
    if (genau) return genau.ab + Math.min(versatz, genau.knoten.length);
    const ziel = knoten.nodeType === Node.TEXT_NODE ? knoten : (knoten.childNodes[versatz] ?? knoten);
    const danach = this.#stuecke.find((s) => (ziel.compareDocumentPosition(s.knoten) & (Node.DOCUMENT_POSITION_FOLLOWING | Node.DOCUMENT_POSITION_CONTAINED_BY)) > 0);
    return danach ? danach.ab : this.text.length;
  }
}
