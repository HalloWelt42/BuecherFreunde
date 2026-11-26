// Feste Bereiche (StaticRange) für alles, was lange auf dem Blatt steht: Markierungen und Treffer. Einen mitlaufenden
// Bereich (Range) führt der Browser bei jeder Änderung am Dokument nach, solange es ihn gibt; tausend davon machen jedes
// Einfügen, Entfernen und Ändern von Text teuer (BF-47). Feste Bereiche rühren sich nicht. Gemessen werden sie mit einem
// einzigen mitlaufenden Bereich je Dokument, der danach wieder leer am Anfang liegt und nichts festhält.
import type { Zeichenstelle } from "./textsuche";

export function festerBereich(von: Zeichenstelle, bis: Zeichenstelle): StaticRange {
  return new StaticRange({ startContainer: von.knoten, startOffset: von.versatz, endContainer: bis.knoten, endOffset: bis.versatz });
}

const MESSER = new WeakMap<Document, Range>();

const mitlaufend = (b: AbstractRange): b is Range => "getClientRects" in b;

/** Misst einen Bereich; ein fester, der nicht mehr passt (Text gekürzt), ergibt nichts, einer außerhalb des Dokuments keine Rechtecke */
function miss<T>(b: AbstractRange, tun: (r: Range) => T, leer: T): T {
  if (mitlaufend(b)) return tun(b);
  const dok = b.startContainer.ownerDocument;
  if (!dok) return leer;
  let r = MESSER.get(dok);
  if (!r) {
    r = dok.createRange();
    MESSER.set(dok, r);
  }
  try {
    r.setStart(b.startContainer, b.startOffset);
    r.setEnd(b.endContainer, b.endOffset);
    return tun(r);
  } catch {
    return leer;
  } finally {
    r.setStart(dok, 0);
    r.collapse(true);
  }
}

export const rechteckeVon = (b: AbstractRange): DOMRect[] => miss(b, (r) => [...r.getClientRects()], []);

export const umrissVon = (b: AbstractRange): DOMRect | null => miss(b, (r) => r.getBoundingClientRect(), null);

export const textVon = (b: AbstractRange): string => miss(b, (r) => r.toString(), "");
