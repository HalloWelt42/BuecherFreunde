// Marken am Rand des Blatts: Notizen, Markierungen und Etiketten als bunte Streifen. Die der offenen Seite stehen breit auf
// Höhe ihrer Stelle, alle übrigen schmal an festem Platz (oben der Anfang des Buchs, unten das Ende). Nie übereinander.
import type { Etikett, Markierung, Notiz } from "../typen";
import { istDunkel } from "./darstellung";
import { markierungsort, markierungstext } from "./typen";

export type Randart = "Markierung" | "Notiz" | "Etikett";

export interface Randeintrag {
  schluessel: string;
  art: Randart;
  farbe: string;
  text: string;
  /** Für Menschen: "Seite 48", "62 %" */
  ort: string;
  seite: number | null;
  prozent: number | null;
  cfi: string;
  quelle: Markierung | Notiz | (Etikett & { page_reference?: string; position_percent?: number; cfi_reference?: string });
}

export const NOTIZFARBE = "#FFD54A";

function lies(ort: string | number | null | undefined, cfi: string | null | undefined, prozent?: number | null) {
  const s = String(ort ?? "").trim();
  const seite = Number(cfi?.match(/^page:(\d+)/)?.[1] ?? s.match(/^(?:S\.|Seite\s*)?\s*(\d+)$/i)?.[1] ?? NaN);
  const p = Number(cfi?.match(/^percent:([\d.]+)/)?.[1] ?? s.match(/([\d.,]+)\s*%/)?.[1]?.replace(",", ".") ?? prozent ?? NaN);
  return { seite: Number.isFinite(seite) && seite > 0 ? seite : null, prozent: Number.isFinite(p) ? p : null, cfi: cfi?.startsWith("epubcfi") ? cfi : "" };
}

const ortVon = (seite: number | null, prozent: number | null, roh: string) => (seite ? `Seite ${seite}` : prozent !== null ? `${Math.round(prozent)} %` : roh);

export function randeintraege(markierungen: Markierung[], notizen: Notiz[], etiketten: Randeintrag["quelle"][]): Randeintrag[] {
  const aus: Randeintrag[] = [];
  for (const m of markierungen) {
    const l = lies("", m.cfi_range);
    aus.push({ schluessel: `m${m.id}`, art: "Markierung", farbe: m.color || "#FFEE58", text: m.label_note || m.label_name || markierungstext(m), ort: markierungsort(m) || ortVon(l.seite, l.prozent, ""), ...l, quelle: m });
  }
  for (const n of notizen) {
    const l = lies(n.page_reference, n.cfi_reference);
    if (l.seite === null && l.prozent === null && !l.cfi) continue;
    aus.push({ schluessel: `n${n.id}`, art: "Notiz", farbe: NOTIZFARBE, text: n.content, ort: ortVon(l.seite, l.prozent, String(n.page_reference ?? "")), ...l, quelle: n });
  }
  for (const e of etiketten as (Etikett & { page_reference?: string; position_percent?: number; cfi_reference?: string })[]) {
    const l = lies(e.page_reference, e.cfi_reference, e.position_percent);
    if (l.seite === null && l.prozent === null && !l.cfi) continue;
    aus.push({ schluessel: `e${e.id}`, art: "Etikett", farbe: e.color || "#4FC3F7", text: [e.name, e.note].filter(Boolean).join(": ") || "Etikett", ort: ortVon(l.seite, l.prozent, e.page_reference ?? ""), ...l, quelle: e });
  }
  return aus;
}

/** Schrift auf der Marke, hell oder dunkel, je nach Farbe */
export const schriftAuf = (farbe: string) => (istDunkel(farbe) ? "#ffffff" : "#1b1206");

export interface Gelegt<T> {
  y: number;
  eintraege: T[];
}

/**
 * Schmale Marken an festem Platz: y nach dem Anteil im Buch. Wer dort keinen Platz hat, rückt nach unten (oder nach oben, wenn
 * unten keiner ist); sind es mehr als Plätze, fassen nahe Marken sich zu einer zusammen. gesperrt: wo schon breite Marken stehen.
 */
export function legeFest<T>(eintraege: { anteil: number; eintrag: T }[], hoehe: number, marke: number, abstand: number, gesperrt: [number, number][] = []): Gelegt<T>[] {
  const plaetze = Math.max(1, Math.floor((hoehe + abstand) / (marke + abstand)));
  const schritt = marke + abstand;
  const belegt = new Map<number, T[]>();
  const frei = (p: number) => !belegt.has(p) && !gesperrt.some(([von, bis]) => p * schritt < bis + abstand && p * schritt + marke > von - abstand);
  const sortiert = eintraege.toSorted((a, b) => a.anteil - b.anteil);
  for (const { anteil, eintrag } of sortiert) {
    const wunsch = Math.min(plaetze - 1, Math.max(0, Math.round(anteil * (plaetze - 1))));
    let platz = -1;
    for (let d = 0; d < plaetze && platz < 0; d++) {
      if (wunsch + d < plaetze && frei(wunsch + d)) platz = wunsch + d;
      else if (wunsch - d >= 0 && frei(wunsch - d)) platz = wunsch - d;
    }
    // Kein freier Platz mehr: zur nächsten schmalen Marke dazu
    if (platz < 0) platz = [...belegt.keys()].sort((a, b) => Math.abs(a - wunsch) - Math.abs(b - wunsch))[0] ?? wunsch;
    belegt.set(platz, [...(belegt.get(platz) ?? []), eintrag]);
  }
  return [...belegt].sort((a, b) => a[0] - b[0]).map(([p, liste]) => ({ y: p * schritt, eintraege: liste }));
}

/** Breite Marken auf Höhe ihrer Stelle, innerhalb des sichtbaren Bereichs, untereinander statt übereinander */
export function legeAnStelle<T>(eintraege: { y: number; eintrag: T }[], oben: number, unten: number, marke: number, abstand: number): Gelegt<T>[] {
  const sortiert = eintraege.toSorted((a, b) => a.y - b.y);
  const ys = sortiert.map((e) => Math.min(unten - marke, Math.max(oben, e.y)));
  for (let i = 1; i < ys.length; i++) ys[i] = Math.max(ys[i], ys[i - 1] + marke + abstand);
  // Unten zu wenig Platz: von unten her wieder hochschieben
  for (let i = ys.length - 1; i >= 0; i--) ys[i] = Math.min(ys[i], (i === ys.length - 1 ? unten : ys[i + 1] - abstand) - marke);
  // Reicht der Platz gar nicht, fassen die letzten sich zusammen
  const aus: Gelegt<T>[] = [];
  sortiert.forEach((e, i) => {
    if (aus.length && ys[i] < oben) aus[aus.length - 1].eintraege.push(e.eintrag);
    else aus.push({ y: Math.max(oben, ys[i]), eintraege: [e.eintrag] });
  });
  return aus;
}
