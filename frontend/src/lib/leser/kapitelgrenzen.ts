// Was ein Kapitel ist, wenn das Verzeichnis tiefer gegliedert ist: die oberste Ebene mit wenigstens drei Einträgen. So zählt
// bei Teilen mit Kapiteln das Kapitel, nicht der Teil.
import type { Kapitel } from "./typen";

export function kapitelebene(k: Kapitel[]): number {
  const tiefste = Math.max(0, ...k.map((x) => x.tiefe));
  for (let e = 0; e <= tiefste; e++) if (k.filter((x) => x.tiefe <= e).length >= 3) return e;
  return tiefste;
}

/** Das Kapitel, in dem Eintrag n liegt, und das nächste; -1, wenn n vor dem ersten liegt */
export function kapitelUm(k: Kapitel[], n: number): [number, number | null] {
  const e = kapitelebene(k);
  let anfang = -1;
  for (let i = Math.min(n, k.length - 1); i >= 0; i--) {
    if (k[i].tiefe <= e) {
      anfang = i;
      break;
    }
  }
  const naechstes = k.findIndex((x, i) => i > anfang && x.tiefe <= e);
  return [anfang, naechstes < 0 ? null : naechstes];
}
