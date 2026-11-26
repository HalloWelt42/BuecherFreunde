// Ein Lesefluss bewegt durch einen Text: gescrollt oder Schirm für Schirm geblättert. Die Leser kennen nur diese Griffe.
import type { Anker } from "./textmass";

export type Leseart = "blaettern" | "scrollen";

/** Wohin gesprungen wird */
export type Ziel = Element | AbstractRange | Anker;

export interface Lesefluss {
  readonly art: Leseart;
  /** Anteil des Textes vor dem Schirm, 0 bis 1; am Ende 1 */
  readonly anteil: number;
  readonly amAnfang: boolean;
  readonly amEnde: boolean;
  /** Einen Schirm weiter oder zurück; false am Rand des Textes */
  vor(): boolean;
  zurueck(): boolean;
  zuAnteil(anteil: number): void;
  zu(ziel: Ziel): void;
  /** Erste Stelle auf dem Schirm */
  stelle(): Anker | null;
  /** Erste Stelle nach dem Schirm; null am Ende */
  ende(): Anker | null;
  /** Steht die Stelle auf dem Schirm? */
  zeigt(a: Anker): boolean;
  /** Die Stelle, an der man liest: wohin zuletzt geblättert oder gesprungen wurde */
  halt(): Anker | null;
  /** Diese Stelle festhalten, auch wenn noch nie bewegt wurde (vor einem Umbau) */
  halteFest(): void;
  /** Schirme vor und nach diesem, zum Nachladen */
  readonly davor: number;
  readonly danach: number;
  /** Hat man das Element erreicht (auf dem Schirm oder davor)? */
  erreicht(e: Element): boolean;
  /** Der Text ist neu umbrochen oder ergänzt: dieselbe Stelle bleibt stehen */
  neu(): void;
  zerstoere(): void;
}

export function alsAnker(ziel: Ziel, anfangVon: (e: Node) => Anker | null): Anker | null {
  if ("knoten" in ziel) return ziel;
  if ("startContainer" in ziel) {
    const k = ziel.startContainer;
    return k.nodeType === Node.TEXT_NODE ? { knoten: k, versatz: ziel.startOffset } : anfangVon(k.childNodes[ziel.startOffset] ?? k);
  }
  return anfangVon(ziel);
}
