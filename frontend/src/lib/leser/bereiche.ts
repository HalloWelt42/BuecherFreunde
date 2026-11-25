// Bereiche im Text zu einem Wortlaut, wenn Lage und Text nicht aus derselben Quelle stammen (PDF: Textebene, Textansicht)
import { textknoten } from "./text/markierung";
import { findeZeichen } from "./textsuche";

/** Der Wortlaut in der Wurzel, nahe diesem Anteil */
export function bereichZu(wurzel: Element, wortlaut: string, anteil: number): Range | null {
  const ort = findeZeichen(textknoten(wurzel), wortlaut, anteil);
  if (!ort) return null;
  const r = wurzel.ownerDocument.createRange();
  r.setStart(ort.von.knoten, ort.von.versatz);
  r.setEnd(ort.bis.knoten, ort.bis.versatz);
  return r;
}

/** Ein Zeichen im Bereich bei diesem Anteil seiner Buchstaben, als eigener kleiner Bereich */
export function zeichenIn(bereich: Range, anteil: number): Range {
  const dok = bereich.startContainer.ownerDocument!;
  const knoten = textknoten(bereich.commonAncestorContainer.nodeType === Node.TEXT_NODE ? bereich.commonAncestorContainer.parentNode! : bereich.commonAncestorContainer).filter((k) => bereich.intersectsNode(k));
  const stellen: [Text, number][] = [];
  for (const k of knoten) {
    const von = k === bereich.startContainer ? bereich.startOffset : 0;
    const bis = k === bereich.endContainer ? bereich.endOffset : k.length;
    for (let i = von; i < bis; i++) if (!/\s/.test(k.data[i])) stellen.push([k, i]);
  }
  const r = dok.createRange();
  const s = stellen[Math.min(stellen.length - 1, Math.floor(anteil * stellen.length))];
  if (!s) return bereich;
  r.setStart(s[0], s[1]);
  r.setEnd(s[0], s[1] + 1);
  return r;
}
