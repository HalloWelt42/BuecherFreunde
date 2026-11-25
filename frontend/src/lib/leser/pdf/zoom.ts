// Zoomstufen und Einpassen der PDF-Seiten
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

const FUGE_DOPPEL = 16;

/** Maß, mit dem eine Seite in die freie Fläche passt; null, wenn die Fläche gerade verborgen ist */
export function einpassen(ansicht: Ansicht, seite: Mass, flaeche: Mass): number | null {
  if (flaeche.breite <= 0 || flaeche.hoehe <= 0) return null;
  const hoch = flaeche.hoehe / seite.hoehe;
  switch (ansicht) {
    case "breite":
      return flaeche.breite / seite.breite;
    case "seite":
    case "einzeln":
      return Math.min(flaeche.breite / seite.breite, hoch);
    case "doppel":
      return Math.min((flaeche.breite - FUGE_DOPPEL) / (seite.breite * 2), hoch);
    default:
      return null;
  }
}

/** Seiten, die in Einzel- und Doppelansicht zu sehen sind */
export function sichtbareSeiten(ansicht: Ansicht, seite: number, gesamt: number): number[] {
  if (ansicht === "einzeln") return [seite];
  const links = seite % 2 === 0 ? seite - 1 : seite;
  return [links, links + 1].filter((n) => n >= 1 && n <= gesamt);
}

export const geblaettert = (a: Ansicht) => a === "einzeln" || a === "doppel";
