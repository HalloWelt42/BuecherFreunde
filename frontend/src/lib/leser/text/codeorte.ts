// Wo die Codestellen in einem Text stehen (BF-29), für die Tasten über dem Buch: in Markdown und EPUB die Codeblöcke (pre),
// deren Text eine erkannte Stelle ist; in schlichtem Text die Zeile, mit der die Stelle beginnt.
import type { Codestelle } from "../../api/ausfuehren";

export interface Codelage {
  stelle: Codestelle;
  teil: number;
  lage: DOMRect;
}

/** Verglichen ohne Leerraum: Färbung, Einrückung und Zeilenenden setzen ihn verschieden */
const gleich = (t: string) => t.replace(/\s+/g, "");

/** Codeblöcke eines Dokuments, deren Text eine Stelle ist; versatz: Lage seines Rahmens im Fenster (EPUB) */
export function codebloecke(wurzel: ParentNode, stellen: readonly Codestelle[], versatz = { x: 0, y: 0 }): Codelage[] {
  if (!stellen.length) return [];
  const nach = new Map(stellen.map((s) => [gleich(s.code), s]));
  const aus: Codelage[] = [];
  for (const pre of wurzel.querySelectorAll("pre")) {
    const s = nach.get(gleich(pre.querySelector("code")?.textContent ?? pre.textContent ?? ""));
    if (!s) continue;
    const r = pre.getBoundingClientRect();
    aus.push({ stelle: s, teil: 0, lage: new DOMRect(r.left + versatz.x, r.top + versatz.y, r.width, r.height) });
  }
  return aus;
}

/** Schlichter Text in Blöcken (ein Textknoten je Block, Zeilen mit \n): Anfang der Zeile n (ab 1) als Bereich */
export function zeilenbereich(bloecke: readonly Element[], zeile: number): Range | null {
  let erste = 1;
  for (const b of bloecke) {
    const k = b.firstChild;
    if (!k || k.nodeType !== Node.TEXT_NODE) continue;
    const text = (k as Text).data;
    const zeilen = text.split("\n").length;
    if (zeile < erste + zeilen) {
      let stelle = 0;
      for (let n = erste; n < zeile; n++) stelle = text.indexOf("\n", stelle) + 1;
      const ende = text.indexOf("\n", stelle);
      const r = document.createRange();
      r.setStart(k, stelle);
      r.setEnd(k, ende < 0 ? text.length : ende);
      return r;
    }
    erste += zeilen;
  }
  return null;
}

/** Codestellen im schlichten Text: je Stelle die Lage ihrer ersten Zeile, so breit wie eine Spalte des Satzes */
export function codezeilen(satz: HTMLElement, stellen: readonly Codestelle[], bereiche: Map<string, Range | null>): Codelage[] {
  const spalte = Number.parseFloat(getComputedStyle(satz).columnWidth) || satz.getBoundingClientRect().width;
  const bloecke = [...satz.querySelectorAll(".schlichttext")];
  const aus: Codelage[] = [];
  for (const s of stellen) {
    const zeile = s.teile[0]?.zeile;
    if (!zeile) continue;
    if (!bereiche.has(s.kennung)) bereiche.set(s.kennung, zeilenbereich(bloecke, zeile));
    const r = bereiche.get(s.kennung)?.getClientRects()[0];
    if (r) aus.push({ stelle: s, teil: 0, lage: new DOMRect(r.left, r.top, spalte, r.height) });
  }
  return aus;
}
