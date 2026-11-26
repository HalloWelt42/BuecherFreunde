// Zur vorigen und nächsten Stelle mit Notiz, Markierung oder Etikett (BF-63): nach dem Anteil im Buch, vom Stand aus. Wer
// eben zu einer Stelle gesprungen ist und dort steht, geht von ihr weiter, auch zu Stellen auf derselben Seite.
import type { Markierung } from "../typen";
import type { Randeintrag } from "./randmarken";
import type { Lesesitzung, Randort } from "./sitzung.svelte";

/** So nah am Stand liegt eine Stelle hier, nicht davor oder danach */
export const NAHE = 0.0005;
/** So weit darf sich der Stand nach einem Sprung bewegen, und die Stelle gilt noch als die, an der man steht */
export const NOCH_DORT = 0.002;

export interface Stelle {
  eintrag: Randeintrag;
  anteil: number;
}

/** Die Stellen mit bekanntem Anteil, nach ihrem Anteil im Buch */
export function ordne(eintraege: Randeintrag[], anteil: (e: Randeintrag) => number | null): Stelle[] {
  const aus: Stelle[] = [];
  for (const eintrag of eintraege) {
    const a = anteil(eintrag);
    if (a !== null && Number.isFinite(a)) aus.push({ eintrag, anteil: a });
  }
  return aus.sort((x, y) => x.anteil - y.anteil);
}

/** Die nächste Stelle in der Richtung (1 vor, -1 zurück) oder null */
export function ziel(stellen: Stelle[], stand: number, zuletzt: string, richtung: 1 | -1): Stelle | null {
  const dort = stellen.findIndex((s) => s.eintrag.schluessel === zuletzt);
  if (dort >= 0 && Math.abs(stellen[dort].anteil - stand) <= NOCH_DORT) return stellen[dort + richtung] ?? null;
  if (richtung === 1) return stellen.find((s) => s.anteil > stand + NAHE) ?? null;
  return stellen.findLast((s) => s.anteil < stand - NAHE) ?? null;
}

/** Zu einem Eintrag springen, wie die Marke am Rand */
export function springe(sitzung: Lesesitzung, e: Randeintrag): void {
  const g = sitzung.griffe;
  if (e.art === "Markierung") g?.zurMarkierung(e.quelle as Markierung);
  else g?.zurStelle(e.seite ? `S.${e.seite}` : e.ort, e.cfi, e.prozent ?? 0);
}

/** Springt zur nächsten Stelle in der Richtung und klappt ihre Karte am Rand auf */
export function springeWeiter(sitzung: Lesesitzung, rand: Randort, stellen: Stelle[], richtung: 1 | -1): boolean {
  const s = ziel(stellen, rand.stand(), sitzung.gesprungen, richtung);
  if (!s) return false;
  sitzung.randOffen = "";
  springe(sitzung, s.eintrag);
  sitzung.gesprungen = s.eintrag.schluessel;
  sitzung.randOffen = s.eintrag.schluessel;
  return true;
}
