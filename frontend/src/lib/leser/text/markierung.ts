// Markierungen und Treffer im Text eines Blatts (MD, TXT, PDF als Text): über ihren Wortlaut gefunden, in der Nähe der
// gemerkten Stelle. Gemalt wird mit Hervorhebungen, der Text selbst bleibt unberührt. Die Bereiche sind fest
// (lib/leser/festbereich.ts): sie bleiben, bis neu gezeichnet wird, ohne jede Änderung am Dokument mitzumachen.
import type { Markierung } from "../../typen";
import { durchsichtig, VORGABE_STIFT } from "../farben";
import { festerBereich } from "../festbereich";
import { hebeHervor, type Hervorhebungsart, type Rechteckschicht } from "../hervorhebung";
import { Zeichenindex } from "../textsuche";

export function textknoten(flaeche: Node): Text[] {
  const geher = document.createTreeWalker(flaeche, NodeFilter.SHOW_TEXT, { acceptNode: (k) => (k.parentElement?.closest(".hervorhebungen, button, [hidden]") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
  const aus: Text[] = [];
  while (geher.nextNode()) aus.push(geher.currentNode as Text);
  return aus;
}

export const TREFFER: Hervorhebungsart = { name: "bf-treffer", farbe: "rgba(255, 152, 0, 0.45)", rang: 2 };
/** Art eines Stifts: je Farbe eine, in allen Ansichten gleich benannt */
export const stiftart = (farbe: string): Hervorhebungsart => ({ name: `bf-stift-${farbe.replace(/[^0-9a-z]/gi, "")}`, farbe: durchsichtig(farbe, 0.4), rang: 1 });
/** Welche Arten von Stiften gerade gemalt sind, je Fläche, damit sie wieder weggehen */
const GEMALT = new WeakMap<Document, Hervorhebungsart[]>();

export function prozentVon(cfi: string | undefined): number | null {
  const p = cfi?.match(/^percent:([\d.]+)/)?.[1];
  return p === undefined ? null : Number(p);
}

/** Malt die Markierungen; liefert ihre Bereiche je Kennung, zum Hinspringen. wurzel: wo eine Markierung zu suchen ist (etwa ihre Seite) */
export function zeichneMarkierungen(flaeche: HTMLElement, markierungen: Markierung[], ersatz?: Rechteckschicht, wurzel: (m: Markierung) => HTMLElement | null = () => flaeche): Map<number, StaticRange> {
  const indexVon = new Map<HTMLElement, Zeichenindex>();
  const aus = new Map<number, StaticRange>();
  const je = new Map<string, { art: Hervorhebungsart; bereiche: StaticRange[] }>();
  for (const m of markierungen) {
    const w = wurzel(m);
    if (!w) continue;
    if (!indexVon.has(w)) indexVon.set(w, new Zeichenindex(textknoten(w)));
    const p = prozentVon(m.cfi_range);
    const ort = indexVon.get(w)!.finde(m.text_snippet ?? "", p === null ? null : p / 100);
    if (!ort) continue;
    const r = festerBereich(ort.von, ort.bis);
    aus.set(m.id, r);
    const art = stiftart(m.color || VORGABE_STIFT);
    const gruppe = je.get(art.name) ?? { art, bereiche: [] };
    gruppe.bereiche.push(r);
    je.set(art.name, gruppe);
  }
  const dok = flaeche.ownerDocument;
  for (const alt of GEMALT.get(dok) ?? []) if (!je.has(alt.name)) hebeHervor(dok, alt, [], ersatz);
  for (const { art, bereiche } of je.values()) hebeHervor(dok, art, bereiche, ersatz);
  GEMALT.set(dok, [...je.values()].map((g) => g.art));
  return aus;
}

/** Ein Wortlaut, auch über mehrere Textknoten */
export function zeichneWortlaut(flaeche: HTMLElement, wortlaut: string, ersatz?: Rechteckschicht): StaticRange | null {
  const ort = new Zeichenindex(textknoten(flaeche)).finde(wortlaut.replace(/^"|"$/g, ""), null);
  const r = ort && festerBereich(ort.von, ort.bis);
  hebeHervor(flaeche.ownerDocument, TREFFER, r ? [r] : [], ersatz);
  return r;
}

/** Alle Stellen eines Suchworts (höchstens so viele), in Lesefolge */
export function zeichneTreffer(flaeche: HTMLElement, wort: string, hoechstens = 500, ersatz?: Rechteckschicht): StaticRange[] {
  const gesucht = wort.trim().replace(/^"|"$/g, "").toLowerCase();
  const aus: StaticRange[] = [];
  if (gesucht.length >= 2) {
    for (const k of textknoten(flaeche)) {
      const klein = k.data.toLowerCase();
      for (let i = klein.indexOf(gesucht); i >= 0 && aus.length < hoechstens; i = klein.indexOf(gesucht, i + gesucht.length)) aus.push(festerBereich({ knoten: k, versatz: i }, { knoten: k, versatz: i + gesucht.length }));
    }
  }
  hebeHervor(flaeche.ownerDocument, TREFFER, aus, ersatz);
  return aus;
}

/** Überschriften als Verzeichnis: im Markdown aus dem Dokument, im Text aus Zeilen, die wie Überschriften aussehen */
export function textkapitel(zeilen: string[]): { titel: string; anteil: number }[] {
  const muster = /^(?:(?:kapitel|teil|abschnitt|buch|akt|szene|chapter|part)\b.{0,60}|\d{1,3}(?:\.\d{1,3}){0,3}\.?\s+\S.{2,70})$/i;
  const aus: { titel: string; zeichen: number }[] = [];
  let zeichen = 0;
  zeilen.forEach((z, n) => {
    const t = z.trim();
    const frei = !zeilen[n - 1]?.trim() && !zeilen[n + 1]?.trim();
    if (t && frei && muster.test(t)) aus.push({ titel: t, zeichen });
    zeichen += z.length + 1;
  });
  return aus.length >= 2 && aus.length <= 300 ? aus.map((k) => ({ titel: k.titel, anteil: k.zeichen / zeichen })) : [];
}
