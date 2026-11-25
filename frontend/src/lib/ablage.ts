// Wo die Datei eines Buchs liegt, in Worten
import type { Wolkenablage } from "./typen";

export function ablageText(w: Wolkenablage): string {
  if (w.in_der_wolke === false) return w.pfad === "auf dem Gerät" ? "auf dem Gerät" : w.pfad;
  return `Kellerwolke, ${w.pfad}`;
}
