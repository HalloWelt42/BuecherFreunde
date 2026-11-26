// Zoomstufen und Einpassen der PDF-Seiten
import type { Leseart } from "../fluss/fluss";

export const STUFEN = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];

export type Ansicht = "scroll" | "breite" | "seite" | "doppel" | "einzeln";
export const ANSICHTEN: [Ansicht | "text", string][] = [["scroll", "Fortlaufend"], ["breite", "Seitenbreite"], ["seite", "Ganze Seite"], ["doppel", "Doppelseite"], ["einzeln", "Einzelseite"], ["text", "Nur Text"]];

export function ansichtOder(wert: string | undefined, vorgabe: Ansicht): Ansicht {
  return ANSICHTEN.some(([a]) => a === wert && a !== "text") ? (wert as Ansicht) : vorgabe;
}

/** Nächste Stufe über oder unter dem Maß, auch wenn es zwischen zwei Stufen liegt (Seitenbreite) */
export function naechsteStufe(mass: number, richtung: 1 | -1): number {
  const spiel = 0.005;
  if (richtung > 0) return STUFEN.find((s) => s > mass + spiel) ?? STUFEN[STUFEN.length - 1];
  return [...STUFEN].reverse().find((s) => s < mass - spiel) ?? STUFEN[0];
}

export interface Mass {
  breite: number;
  hoehe: number;
}

/** Lässt sich die geblätterte Seite selbst noch schieben (vergrößert, Querformat)? */
export interface Seitenrest {
  oben: boolean;
  unten: boolean;
}

const FUGE_DOPPEL = 16;
/** Darunter ist eine ganze Seite unlesbar klein (Telefon quer): dann gilt die Breite, geblättert wird in Abschnitten */
const NIEDRIG = 480;

/** Maß, mit dem eine Seite in die freie Fläche passt; null, wenn die Fläche gerade verborgen ist. hoechstens: so breit
 *  wird eine Seite höchstens (Breite des Blatts); in der Doppelseite gilt es für jede der beiden */
export function einpassen(ansicht: Ansicht, seite: Mass, flaeche: Mass, hoechstens = Infinity): number | null {
  if (flaeche.breite <= 0 || flaeche.hoehe <= 0) return null;
  const hoch = flaeche.hoehe / seite.hoehe;
  const breit = Math.min(flaeche.breite, hoechstens) / seite.breite;
  switch (ansicht) {
    case "breite":
      return breit;
    case "einzeln":
      return flaeche.hoehe < NIEDRIG && flaeche.breite > flaeche.hoehe ? breit : Math.min(breit, hoch);
    case "seite":
      return Math.min(breit, hoch);
    case "doppel":
      return Math.min(Math.min((flaeche.breite - FUGE_DOPPEL) / 2, hoechstens) / seite.breite, hoch);
    default:
      return null;
  }
}

export const geblaettert = (a: Ansicht) => a === "einzeln" || a === "doppel";

export const artVon = (a: Ansicht): Leseart => (geblaettert(a) ? "blaettern" : "scrollen");

/** Womit ein Buch ohne eigene Ansicht beginnt */
export const ansichtFuer = (art: Leseart, telefon: boolean): Ansicht => (art === "blaettern" ? "einzeln" : telefon ? "breite" : "scroll");

/** Seiten, die in Einzel- und Doppelansicht zu sehen sind */
export function sichtbareSeiten(ansicht: Ansicht, seite: number, gesamt: number): number[] {
  if (ansicht === "einzeln") return [seite];
  const links = seite % 2 === 0 ? seite - 1 : seite;
  return [links, links + 1].filter((n) => n >= 1 && n <= gesamt);
}

/** Der Bogen danach und davor, ohne den sichtbaren */
export function nachbarn(ansicht: Ansicht, seite: number, gesamt: number): number[][] {
  const schritt = ansicht === "doppel" ? 2 : 1;
  const erste = sichtbareSeiten(ansicht, seite, gesamt)[0] ?? seite;
  return [erste + schritt, erste - schritt].filter((n) => n >= 1 && n <= gesamt).map((n) => sichtbareSeiten(ansicht, n, gesamt));
}
