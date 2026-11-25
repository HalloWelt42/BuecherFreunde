// Was der Fokus braucht: den Absatz unter einem Punkt oder um eine Stelle, und die vier Streifen um ein klares Fenster. Nichts
// davon rührt den Text an; der Fokus ist eine Schicht darüber.

export interface Kasten {
  links: number;
  oben: number;
  rechts: number;
  unten: number;
}

const BLOECKE = "p, li, h1, h2, h3, h4, h5, h6, blockquote, pre, figure, figcaption, table, dt, dd, .abbildung, .kasten, .hinweis";

/** Das Rechteck eines Elements in der Spalte, in der x liegt (geblättert steht ein Absatz oft in zwei Spalten) */
function inSpalte(rects: DOMRectList | DOMRect[], x: number | null): Kasten | null {
  const liste = [...rects].filter((r) => r.width && r.height);
  if (!liste.length) return null;
  const spalte = x === null ? liste : liste.filter((r) => x >= r.left - 4 && x <= r.right + 4);
  const wahl = spalte.length ? spalte : [liste[0]];
  return { links: Math.min(...wahl.map((r) => r.left)), oben: Math.min(...wahl.map((r) => r.top)), rechts: Math.max(...wahl.map((r) => r.right)), unten: Math.max(...wahl.map((r) => r.bottom)) };
}

function caret(dok: Document, x: number, y: number): { knoten: Node; versatz: number } | null {
  const d = dok as Document & { caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null };
  const p = d.caretPositionFromPoint?.(x, y);
  if (p) return { knoten: p.offsetNode, versatz: p.offset };
  const r = dok.caretRangeFromPoint?.(x, y);
  return r ? { knoten: r.startContainer, versatz: r.startOffset } : null;
}

/** Absatz um eine Stelle: das Block-Element, in schlichtem Text die Zeilen zwischen zwei Leerzeilen */
export function absatzUm(knoten: Node, versatz: number, x: number | null, wurzel: Element): Kasten | null {
  const dok = knoten.ownerDocument!;
  const element = knoten.nodeType === Node.ELEMENT_NODE ? (knoten as Element) : knoten.parentElement;
  const block = element?.closest(BLOECKE);
  if (block && wurzel.contains(block)) return inSpalte(block.getClientRects(), x);
  if (knoten.nodeType !== Node.TEXT_NODE || !wurzel.contains(knoten)) return null;
  const t = (knoten as Text).data;
  const von = t.lastIndexOf("\n\n", Math.max(0, versatz - 1));
  const bis = t.indexOf("\n\n", versatz);
  const r = dok.createRange();
  r.setStart(knoten, von < 0 ? 0 : von + 2);
  r.setEnd(knoten, bis < 0 ? t.length : bis);
  return inSpalte(r.getClientRects(), x);
}

/** Absatz unter einem Punkt im Dokument */
export function absatzBei(dok: Document, x: number, y: number, wurzel: Element): Kasten | null {
  const c = caret(dok, x, y);
  return c ? absatzUm(c.knoten, c.versatz, x, wurzel) : null;
}

export const verschiebe = (k: Kasten, dx: number, dy: number): Kasten => ({ links: k.links + dx, oben: k.oben + dy, rechts: k.rechts + dx, unten: k.unten + dy });

export interface Streifen {
  links: number;
  oben: number;
  breite: number;
  hoehe: number;
  /** Seite, an der der Übergang liegt */
  rand: "oben" | "unten" | "links" | "rechts";
}

/** Vier Streifen um ein klares Fenster, in Lagen der Fläche; der Übergang liegt außen, das Fenster bleibt ganz klar */
export function streifenUm(f: Kasten, breite: number, hoehe: number, _verlauf: number): Streifen[] {
  const o = Math.max(0, Math.min(hoehe, f.oben));
  const u = Math.max(o, Math.min(hoehe, f.unten));
  const l = Math.max(0, Math.min(breite, f.links));
  const r = Math.max(l, Math.min(breite, f.rechts));
  return [
    { links: 0, oben: 0, breite, hoehe: o, rand: "unten" },
    { links: 0, oben: u, breite, hoehe: Math.max(0, hoehe - u), rand: "oben" },
    { links: 0, oben: o, breite: l, hoehe: Math.max(0, u - o), rand: "rechts" },
    { links: r, oben: o, breite: Math.max(0, breite - r), hoehe: Math.max(0, u - o), rand: "links" },
  ];
}

/** Wo gerade vorgelesen wird: der Satz als Zeilenbereich und sein Absatz, im Fenster */
export function vorgelesenIn(dok: Document, wurzel: Element | null, versatz = { x: 0, y: 0 }): { absatz: Kasten | null; zeile: Kasten | null } {
  const f = dok.defaultView as (Window & { CSS?: { highlights?: Map<string, Iterable<Range>> } }) | null;
  const h = f?.CSS?.highlights?.get("bf-vorlesen");
  const r = h ? [...h][0] : undefined;
  if (!r || !wurzel || !r.startContainer.isConnected) return { absatz: null, zeile: null };
  const zeilen = [...r.getClientRects()].filter((q) => q.width);
  const zeile = zeilen.length ? { links: Math.min(...zeilen.map((q) => q.left)), oben: Math.min(...zeilen.map((q) => q.top)), rechts: Math.max(...zeilen.map((q) => q.right)), unten: Math.max(...zeilen.map((q) => q.bottom)) } : null;
  const absatz = absatzUm(r.startContainer, r.startOffset, zeilen[0]?.left ?? null, wurzel);
  return { absatz: absatz && verschiebe(absatz, versatz.x, versatz.y), zeile: zeile && verschiebe(zeile, versatz.x, versatz.y) };
}
