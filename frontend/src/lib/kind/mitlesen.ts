// Mitlesen beim Vorlesen: welches Wort gerade klingt. Die Stimmen des Geräts melden, wo ein Wort beginnt; dann gilt genau dieses
// Wort. Der Sprechdienst schickt je Satz einen Ton ohne Zeitangaben je Wort; dann wird im Satz geschätzt: die Sprechdauer eines
// Wortes wächst mit seinen Silben, nach Komma und Satzende kommt eine kurze Pause.
import { silbenzahl } from "./silben";
import type { Wort } from "./typen";

/** Eine kurze Pause nach einem Satzzeichen, gemessen in Silben */
const PAUSE: [RegExp, number][] = [
  [/[.!?…]["»«)]*$/, 1.2],
  [/[,;:–-]["»«)]*$/, 0.7],
];

/** Das Wort, in dem ein Zeichen steht; zwischen zwei Wörtern das nächste; -1 ohne Wörter */
export function wortBei(woerter: Wort[], zeichen: number): number {
  if (!woerter.length) return -1;
  for (let i = 0; i < woerter.length; i++) if (zeichen < woerter[i].bis) return i;
  return woerter.length - 1;
}

/** Sprechgewicht eines Wortes und die Pause danach */
export function gewicht(wort: Wort, silben: (text: string) => number = silbenzahl): { sprechen: number; pause: number } {
  return { sprechen: Math.max(1, silben(wort.text)), pause: PAUSE.find(([m]) => m.test(wort.text))?.[1] ?? 0 };
}

/** Das geschätzte Wort im Satz, wenn der Anteil (0 bis 1) seiner Dauer gesprochen ist */
export function geschaetztesWort(satzwoerter: Wort[], anteil: number, silben?: (text: string) => number): number {
  if (!satzwoerter.length) return -1;
  const g = satzwoerter.map((w) => gewicht(w, silben));
  // Die Pause nach dem letzten Wort gehört nicht mehr zum Satz
  const gesamt = g.reduce((s, x, i) => s + x.sprechen + (i < g.length - 1 ? x.pause : 0), 0);
  const ziel = Math.min(1, Math.max(0, anteil)) * gesamt;
  let lauf = 0;
  for (let i = 0; i < g.length; i++) {
    lauf += g[i].sprechen;
    if (ziel < lauf) return i;
    lauf += g[i].pause;
    if (ziel < lauf) return i;
  }
  return g.length - 1;
}

/** Die Wörter, die zum Satz gehören (von bis im Text der Einheit) */
export const woerterIm = (woerter: Wort[], von: number, bis: number): Wort[] => woerter.filter((w) => w.bis > von && w.von < bis);
