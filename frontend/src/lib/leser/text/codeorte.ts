// Wo die Codestellen in einem Text stehen (BF-29), für die Tasten über dem Buch: in Markdown und EPUB die Codeblöcke (pre),
// deren Text eine erkannte Stelle ist; in schlichtem Text die Zeile, mit der die Stelle beginnt. Dazu je Block die Zeilen knapp
// über ihm: bis zu ihnen darf die Taste über seine obere Kante ragen, sonst sitzt sie innen (BF-55, stil/leser.css).
import type { Codestelle } from "../../api/ausfuehren";
import { festerBereich, rechteckeVon } from "../festbereich";

export interface Codelage {
  stelle: Codestelle;
  teil: number;
  lage: DOMRect;
  /** Die Zeilen Text knapp über dem Block (Lage im Fenster), die eine Taste auf seiner Kante berühren könnte */
  darueber: DOMRect[];
}

/** So weit über einem Block zählen Zeilen für die Taste auf seiner Kante (mehr als eine halbe Taste in jeder Schrift) */
const REICHWEITE = 80;

/** Freier Platz über einem Kasten bis zur untersten Zeile darüber, die ihn in der Waagerechten berührt */
export function luftUeber(kasten: { top: number; left: number; right: number }, zeilen: Iterable<{ top: number; bottom: number; left: number; right: number; width: number }>): number {
  let unten = Number.NEGATIVE_INFINITY;
  for (const z of zeilen) if (z.width > 0 && z.bottom <= kasten.top + 1 && z.left < kasten.right && z.right > kasten.left) unten = Math.max(unten, z.bottom);
  return unten === Number.NEGATIVE_INFINITY ? Number.POSITIVE_INFINITY : Math.max(0, kasten.top - unten);
}

const zeilenVon = (k: Text) => rechteckeVon(festerBereich({ knoten: k, versatz: 0 }, { knoten: k, versatz: k.length }));

/** Liegt die Zeile über dem Kasten, nah genug und in der Waagerechten auf ihm? */
const knappDarueber = (z: DOMRect, kasten: { top: number; left: number; right: number }) =>
  z.width > 0 && z.bottom <= kasten.top + 1 && z.bottom >= kasten.top - REICHWEITE && z.left < kasten.right && z.right > kasten.left;

/** Die Zeilen knapp über einem Block: der Text davor im Dokument, rückwärts, bis er höher liegt (Markdown, EPUB) */
export function zeilenUeberBlock(block: Element, kasten: { top: number; left: number; right: number } = block.getBoundingClientRect()): DOMRect[] {
  const dok = block.ownerDocument;
  const geher = dok.createTreeWalker(dok.body ?? dok.documentElement, NodeFilter.SHOW_TEXT);
  geher.currentNode = block;
  const aus: DOMRect[] = [];
  for (let n = 0; n < 40 && geher.previousNode(); n++) {
    const k = geher.currentNode as Text;
    if (!/\S/.test(k.data) || k.parentElement?.closest("button, [hidden]")) continue;
    const zeilen = zeilenVon(k).filter((z) => z.width > 0 && z.left < kasten.right && z.right > kasten.left);
    aus.push(...zeilen.filter((z) => knappDarueber(z, kasten)));
    // Was davor steht, liegt noch höher
    if (zeilen.length && zeilen.every((z) => z.bottom < kasten.top - REICHWEITE)) break;
  }
  return aus;
}

const verschoben = (r: DOMRect, um: { x: number; y: number }) => new DOMRect(r.left + um.x, r.top + um.y, r.width, r.height);

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
    aus.push({ stelle: s, teil: 0, lage: verschoben(r, versatz), darueber: zeilenUeberBlock(pre, r).map((z) => verschoben(z, versatz)) });
  }
  return aus;
}

/** Schlichter Text in Blöcken (ein Textknoten je Block, Zeilen mit \n): wo Zeile n (ab 1) steht */
function zeilenstelle(bloecke: readonly Element[], zeile: number): { knoten: Text; von: number; bis: number } | null {
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
      return { knoten: k as Text, von: stelle, bis: ende < 0 ? text.length : ende };
    }
    erste += zeilen;
  }
  return null;
}

/** Anfang der Zeile n (ab 1) als Bereich */
export function zeilenbereich(bloecke: readonly Element[], zeile: number): Range | null {
  const z = zeilenstelle(bloecke, zeile);
  if (!z) return null;
  const r = document.createRange();
  r.setStart(z.knoten, z.von);
  r.setEnd(z.knoten, z.bis);
  return r;
}

/** Wo die erste Zeile einer Stelle steht und die nächsten Zeilen mit Text davor; einmal je Stelle gesucht */
export interface Zeilenorte {
  erste: StaticRange | null;
  davor: StaticRange[];
}

/** Wie viele Zeilen zurück und wie viele mit Text vor einer Stelle gesucht werden */
const DAVOR_ZEILEN = 20;
const DAVOR_MIT_TEXT = 3;

export function zeilenorte(bloecke: readonly Element[], zeile: number): Zeilenorte {
  const fest = (z: ReturnType<typeof zeilenstelle>) => z && festerBereich({ knoten: z.knoten, versatz: z.von }, { knoten: z.knoten, versatz: z.bis });
  const davor: StaticRange[] = [];
  for (let n = zeile - 1; n >= Math.max(1, zeile - DAVOR_ZEILEN) && davor.length < DAVOR_MIT_TEXT; n--) {
    const z = zeilenstelle(bloecke, n);
    if (z && /\S/.test(z.knoten.data.slice(z.von, z.bis))) davor.push(fest(z)!);
  }
  return { erste: fest(zeilenstelle(bloecke, zeile)), davor };
}

/** Codestellen im schlichten Text: je Stelle die Lage ihrer ersten Zeile, so breit wie eine Spalte des Satzes */
export function codezeilen(satz: HTMLElement, stellen: readonly Codestelle[], orte: Map<string, Zeilenorte>): Codelage[] {
  const spalte = Number.parseFloat(getComputedStyle(satz).columnWidth) || satz.getBoundingClientRect().width;
  const bloecke = [...satz.querySelectorAll(".schlichttext")];
  const aus: Codelage[] = [];
  for (const s of stellen) {
    const zeile = s.teile[0]?.zeile;
    if (!zeile) continue;
    if (!orte.has(s.kennung)) orte.set(s.kennung, zeilenorte(bloecke, zeile));
    const o = orte.get(s.kennung)!;
    const r = o.erste && rechteckeVon(o.erste)[0];
    if (!r) continue;
    const lage = new DOMRect(r.left, r.top, spalte, r.height);
    aus.push({ stelle: s, teil: 0, lage, darueber: o.davor.flatMap(rechteckeVon).filter((z) => knappDarueber(z, lage)) });
  }
  return aus;
}
