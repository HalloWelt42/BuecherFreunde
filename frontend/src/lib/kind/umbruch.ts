// Kurze Zeilen für Kinder: höchstens so viele Wörter, wie die Stufe sagt, und nie breiter als die Fläche. Am Anfang des Lesens
// bricht eine Zeile lieber nach einem Sinnschritt um (nach einem Satzzeichen, vor einem Bindewort), solange sie dabei mindestens
// halb voll bleibt. Flattersatz, ohne Trennung am Zeilenende.
import type { Wort } from "./typen";

/** Wie breit ein Text in der Leseschrift ist, in Pixeln */
export type Breitenmass = (text: string) => number;

export interface Zeilengrenzen {
  /** Höchstens so viele Wörter; 0: nur nach Breite */
  woerter: number;
  /** Platz in Pixeln */
  breite: number;
  /** Breite eines Leerraums zwischen zwei Wörtern */
  leer: number;
}

const SATZZEICHEN = /[,.;:!?…)»«"]$/;
const BINDEWOERTER = new Set(["und", "oder", "aber", "denn", "dass", "weil", "wenn", "als", "ob", "bis", "doch", "damit", "sondern", "während", "nachdem", "bevor", "obwohl"]);

const bindewort = (w: Wort | undefined): boolean => !!w && BINDEWOERTER.has(w.text.toLowerCase().replace(/[^\p{L}]/gu, ""));

/** Ende (ausschließlich) der Zeile, die bei Wort `ab` beginnt; immer mindestens ein Wort */
export function zeilenende(woerter: Wort[], ab: number, g: Zeilengrenzen, mass: Breitenmass): number {
  let ende = ab;
  let breite = 0;
  while (ende < woerter.length && (g.woerter === 0 || ende - ab < g.woerter)) {
    const neu = breite + (ende > ab ? g.leer : 0) + mass(woerter[ende].text);
    if (ende > ab && neu > g.breite) break;
    breite = neu;
    ende++;
  }
  if (ende >= woerter.length || g.woerter === 0) return ende;
  // Sinnschritt: der späteste Umbruch nach einem Satzzeichen oder vor einem Bindewort, mit mindestens halber Zeile
  const mindestens = ab + Math.max(1, Math.ceil((ende - ab) / 2));
  for (let k = ende; k >= mindestens; k--) {
    if (SATZZEICHEN.test(woerter[k - 1].text) || bindewort(woerter[k])) return k;
  }
  return ende;
}

/** Alle Zeilen eines Absatzes */
export function zeilenAus(woerter: Wort[], g: Zeilengrenzen, mass: Breitenmass): Wort[][] {
  const aus: Wort[][] = [];
  for (let ab = 0; ab < woerter.length; ) {
    const ende = zeilenende(woerter, ab, g, mass);
    aus.push(woerter.slice(ab, ende));
    ab = ende;
  }
  return aus;
}

/** Wörter eines Textstücks mit ihrer Lage; ab: wo das Stück im Text der Einheit beginnt */
export function woerterAus(text: string, ab = 0): Wort[] {
  return [...text.matchAll(/\S+/g)].map((m) => ({ text: m[0], von: ab + m.index, bis: ab + m.index + m[0].length }));
}
