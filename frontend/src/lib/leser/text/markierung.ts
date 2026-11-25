// Markierungen im Text eines MD- oder TXT-Buchs: über ihren Wortlaut gefunden, in der Nähe der gemerkten Stelle
import type { Markierung } from "../../typen";
import { durchsichtig, VORGABE_STIFT } from "../farben";
import { findeZeichen, type Zeichenstelle } from "../textsuche";

function textknoten(flaeche: HTMLElement): Text[] {
  const geher = document.createTreeWalker(flaeche, NodeFilter.SHOW_TEXT);
  const aus: Text[] = [];
  while (geher.nextNode()) aus.push(geher.currentNode as Text);
  return aus;
}

/** Umhüllt den Bereich, Textknoten für Textknoten; das erste Stück kommt zurück */
function umhuelle(knoten: Text[], von: Zeichenstelle, bis: Zeichenstelle, baue: () => HTMLElement): HTMLElement | null {
  const a = knoten.indexOf(von.knoten);
  const b = knoten.indexOf(bis.knoten);
  let erstes: HTMLElement | null = null;
  for (let i = b; i >= a; i--) {
    const k = knoten[i];
    const anfang = i === a ? von.versatz : 0;
    const ende = i === b ? bis.versatz : k.data.length;
    if (ende <= anfang || !k.data.slice(anfang, ende).trim()) continue;
    const mitte = anfang > 0 ? k.splitText(anfang) : k;
    if (ende - anfang < mitte.data.length) mitte.splitText(ende - anfang);
    const huelle = baue();
    mitte.replaceWith(huelle);
    huelle.append(mitte);
    erstes = huelle;
  }
  return erstes;
}

export function leere(flaeche: HTMLElement, art: string): void {
  for (const h of flaeche.querySelectorAll<HTMLElement>(`mark[data-art="${art}"]`)) h.replaceWith(...h.childNodes);
}

function huelle(art: string, farbe: string, kennung: string): HTMLElement {
  const m = document.createElement("mark");
  m.dataset.art = art;
  m.dataset.markierung = kennung;
  m.style.backgroundColor = farbe;
  return m;
}

export function prozentVon(cfi: string | undefined): number | null {
  const p = cfi?.match(/^percent:([\d.]+)/)?.[1];
  return p === undefined ? null : Number(p);
}

export function zeichneMarkierungen(flaeche: HTMLElement, markierungen: Markierung[]): void {
  leere(flaeche, "markierung");
  for (const m of markierungen) {
    const p = prozentVon(m.cfi_range);
    const knoten = textknoten(flaeche);
    const ort = findeZeichen(knoten, m.text_snippet ?? "", p === null ? null : p / 100);
    if (ort) umhuelle(knoten, ort.von, ort.bis, () => huelle("markierung", durchsichtig(m.color || VORGABE_STIFT, 0.4), String(m.id)));
  }
}

const FARBE_TREFFER = "rgba(255, 152, 0, 0.45)";

/** Ein Wortlaut, auch über mehrere Textknoten; liefert sein erstes Stück */
export function zeichneWortlaut(flaeche: HTMLElement, wortlaut: string): HTMLElement | null {
  leere(flaeche, "treffer");
  const knoten = textknoten(flaeche);
  const ort = findeZeichen(knoten, wortlaut.replace(/^"|"$/g, ""), null);
  return ort && umhuelle(knoten, ort.von, ort.bis, () => huelle("treffer", FARBE_TREFFER, "treffer"));
}

/** Alle Stellen eines Suchworts (höchstens so viele), in Lesefolge */
export function zeichneTreffer(flaeche: HTMLElement, wort: string, hoechstens = 500): HTMLElement[] {
  leere(flaeche, "treffer");
  const gesucht = wort.trim().replace(/^"|"$/g, "").toLowerCase();
  if (gesucht.length < 2) return [];
  const aus: HTMLElement[] = [];
  for (const k of textknoten(flaeche)) {
    const klein = k.data.toLowerCase();
    const stellen: number[] = [];
    for (let i = klein.indexOf(gesucht); i >= 0 && aus.length + stellen.length < hoechstens; i = klein.indexOf(gesucht, i + gesucht.length)) stellen.push(i);
    const eigene: HTMLElement[] = [];
    for (const i of stellen.reverse()) {
      const h = umhuelle([k], { knoten: k, versatz: i }, { knoten: k, versatz: i + gesucht.length }, () => huelle("treffer", FARBE_TREFFER, "treffer"));
      if (h) eigene.unshift(h);
    }
    aus.push(...eigene);
  }
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
