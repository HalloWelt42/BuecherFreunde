// Text in Sätze und in Stücke teilen, mit ihrer Lage
import type { Satz } from "./typen";

const HOECHSTENS = 220;

/** Sätze ohne Leerraum am Rand; überlange an Wortgrenzen */
export function saetzeMitLage(text: string): Satz[] {
  const aus: Satz[] = [];
  const nimm = (von: number, bis: number) => {
    while (von < bis && /\s/.test(text[von])) von++;
    while (bis > von && /\s/.test(text[bis - 1])) bis--;
    while (bis - von > HOECHSTENS) {
      const schnitt = text.lastIndexOf(" ", von + HOECHSTENS);
      const ende = schnitt > von ? schnitt : von + HOECHSTENS;
      aus.push({ text: text.slice(von, ende), von, bis: ende });
      von = ende;
      while (von < bis && /\s/.test(text[von])) von++;
    }
    if (bis > von) aus.push({ text: text.slice(von, bis), von, bis });
  };
  let anfang = 0;
  for (const m of text.matchAll(/(?<=[.!?:;])\s+|\n\s*\n/g)) {
    nimm(anfang, m.index);
    anfang = m.index + m[0].length;
  }
  nimm(anfang, text.length);
  return aus;
}

export const saetze = (text: string): string[] => saetzeMitLage(text.replace(/\s+/g, " ")).map((s) => s.text);

/** Stücke für je eine Anfrage: ganze Sätze, zusammen höchstens so lang (ein einzelner Satz darf länger sein) */
export function stuecke(text: string, hoechstens: number): Satz[] {
  const aus: Satz[] = [];
  for (const s of saetzeMitLage(text)) {
    const letztes = aus.at(-1);
    if (letztes && s.bis - letztes.von <= hoechstens) Object.assign(letztes, { bis: s.bis, text: text.slice(letztes.von, s.bis) });
    else aus.push({ ...s });
  }
  return aus;
}

/** Lage eines Wortlauts ab einer Stelle, ohne auf Leerraum zu achten; findet er sich nicht, gilt seine Länge ab dort */
export function lageAb(text: string, wortlaut: string, ab: number): [number, number] {
  const gesucht = wortlaut.replace(/\s+/g, "");
  if (!gesucht) return [ab, ab];
  const leer = (i: number) => /\s/.test(text[i]);
  // Der Satz folgt fast immer unmittelbar; weit suchen träfe eine spätere Wiederholung
  for (let start = ab; start < Math.min(text.length, ab + 400); start++) {
    if (leer(start) || text[start] !== gesucht[0]) continue;
    let i = start;
    let g = 0;
    while (i < text.length && g < gesucht.length) {
      if (leer(i)) i++;
      else if (text[i] === gesucht[g]) [i, g] = [i + 1, g + 1];
      else break;
    }
    if (g === gesucht.length) return [start, i];
  }
  let von = ab;
  while (von < text.length && leer(von)) von++;
  return [von, Math.min(text.length, von + wortlaut.length)];
}
