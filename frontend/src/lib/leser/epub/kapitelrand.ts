// Gescrollt endet die Fläche mit dem Kapitel. Wer am Rand weiterzieht (Rad, Finger), kommt ins nächste oder vorige.
import { radschritt } from "../blaettergesten";

export interface Kapitelrand {
  /** Gilt gerade das Scrollen? */
  gilt(): boolean;
  /** Liegt der Rand in dieser Richtung schon an? */
  amRand(richtung: 1 | -1): boolean;
  weiter(richtung: 1 | -1): void;
}

const ZUG_AB = 60;

export function kapitelrand(flaeche: EventTarget, rand: Kapitelrand): () => void {
  let start: { y: number; oben: boolean; unten: boolean } | null = null;

  const beginnt = (e: Event) => {
    const t = (e as TouchEvent).touches;
    start = rand.gilt() && t.length === 1 ? { y: t[0].clientY, oben: rand.amRand(-1), unten: rand.amRand(1) } : null;
  };
  // Nur wer schon am Rand stand, zieht weiter; ein Schwung, der dort endet, bleibt stehen
  const endet = (e: Event) => {
    if (!start || !rand.gilt()) return;
    const dy = (e as TouchEvent).changedTouches[0].clientY - start.y;
    const { oben, unten } = start;
    start = null;
    if (unten && dy <= -ZUG_AB) rand.weiter(1);
    else if (oben && dy >= ZUG_AB) rand.weiter(-1);
  };
  const rad = radschritt({ gilt: rand.gilt, vor: () => rand.weiter(1), zurueck: () => rand.weiter(-1), schiebt: (achse, richtung) => achse === "x" || !rand.amRand(richtung) }) as EventListener;

  flaeche.addEventListener("touchstart", beginnt, { passive: true });
  flaeche.addEventListener("touchend", endet, { passive: true });
  flaeche.addEventListener("wheel", rad, { passive: false });
  return () => {
    flaeche.removeEventListener("touchstart", beginnt);
    flaeche.removeEventListener("touchend", endet);
    flaeche.removeEventListener("wheel", rad);
  };
}
