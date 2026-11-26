// Tasten aller Leser. Beim Blättern bewegen auch Leertaste, Pfeil hoch und Pfeil runter einen Schirm; beim Scrollen gehören
// sie der Fläche.
import { imEigenenFenster, schreibtGerade } from "../flucht";
import { istBedienbar } from "./bedienbar";
import type { Leseart } from "./fluss/fluss";

export interface Tastengriffe {
  vor: () => void;
  zurueck: () => void;
  anfang: () => void;
  ende: () => void;
  /** Zeilenweise scrollen, nur wo der Browser es nicht selbst kann (Buchrahmen) */
  zeileVor?: () => void;
  zeileZurueck?: () => void;
  /** Schrift oder Zoom; ohne Griff bleibt die Taste frei */
  groesser?: () => void;
  kleiner?: () => void;
}

/** true, wenn die Taste hier etwas bewirkt hat */
export function blaettertaste(e: KeyboardEvent, art: Leseart, tun: Tastengriffe): boolean {
  if (schreibtGerade(e) || imEigenenFenster(e) || e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return false;
  const griff = waehle(e, art, tun);
  if (!griff) return false;
  e.preventDefault();
  griff();
  return true;
}

function waehle(e: KeyboardEvent, art: Leseart, tun: Tastengriffe): (() => void) | undefined {
  const immer: Record<string, (() => void) | undefined> = { ArrowRight: tun.vor, PageDown: tun.vor, ArrowLeft: tun.zurueck, PageUp: tun.zurueck, Home: tun.anfang, End: tun.ende, "+": tun.groesser, "=": tun.groesser, "-": tun.kleiner };
  if (immer[e.key]) return immer[e.key];
  const blaettert = art === "blaettern";
  if (e.key === "ArrowDown") return blaettert ? tun.vor : tun.zeileVor;
  if (e.key === "ArrowUp") return blaettert ? tun.zurueck : tun.zeileZurueck;
  if (e.key === " " && (blaettert || tun.zeileVor) && !istBedienbar(e.target)) return e.shiftKey ? tun.zurueck : tun.vor;
  return undefined;
}
