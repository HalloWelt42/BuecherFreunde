// Farbthemen, Papiere, Schriften und Regelbereiche aller Leser
export interface Farbthema {
  name: string;
  fg: string;
  bg: string;
  symbol: string;
}

export const FARBTHEMEN: Farbthema[] = [
  { name: "Hell", fg: "#1a1a1a", bg: "#ffffff", symbol: "sun" },
  { name: "Sepia", fg: "#3d2b1f", bg: "#f4ecd8", symbol: "cloud-sun" },
  { name: "Dämmerung", fg: "#c9b99a", bg: "#3d3526", symbol: "cloud-moon" },
  { name: "Dunkel", fg: "#c8c8c8", bg: "#1e1e1e", symbol: "moon" },
  { name: "Nacht", fg: "#8a8a8a", bg: "#0a0a0a", symbol: "star" },
];

/** Ohne eigene Wahl folgt der Leser der Darstellung der App */
export function vorgabeThema(dunkel: boolean): Farbthema {
  return FARBTHEMEN[dunkel ? 3 : 0];
}

export function themaIndex(fg: string, bg: string): number {
  return FARBTHEMEN.findIndex((t) => t.fg === fg && t.bg === bg);
}

/** Dunkler Grund, gerechnet aus der Helligkeit, gilt auch für eigene Farben */
export function istDunkel(bg: string): boolean {
  const n = bg.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => Number.parseInt(n.slice(i, i + 2), 16) || 0);
  return r * 0.299 + g * 0.587 + b * 0.114 < 128;
}

export type Papier = "normal" | "sepia" | "dunkel" | "kontrast";
export const PAPIERE: [Papier, string][] = [["normal", "Hell"], ["sepia", "Sepia"], ["dunkel", "Dunkel"], ["kontrast", "Kontrast"]];

/** Farben des Blatts unter dem Bild einer PDF-Seite, so wie die Papiere sie färben */
export const PAPIERFARBEN: Record<Papier, Pick<Farbthema, "fg" | "bg">> = {
  normal: { fg: "#1a1a1a", bg: "#ffffff" },
  sepia: { fg: "#3c2c16", bg: "#f2f2ee" },
  dunkel: { fg: "#d7d8d0", bg: "#222222" },
  kontrast: { fg: "#ffffff", bg: "#000000" },
};

export function papierOder(wert: string | undefined, dunkel: boolean): Papier {
  return PAPIERE.some(([p]) => p === wert) ? (wert as Papier) : dunkel ? "dunkel" : "normal";
}

export { gleicheSchrift } from "./schriften";

export interface Bereich {
  min: number;
  max: number;
  schritt: number;
  vorgabe: number;
}

export const GROESSE: Bereich = { min: 50, max: 300, schritt: 5, vorgabe: 100 };
export const ZEILEN: Bereich = { min: 1, max: 3, schritt: 0.1, vorgabe: 1.6 };

export function klemme(wert: number, { min, max, schritt }: Bereich): number {
  const gerundet = Math.round(wert / schritt) * schritt;
  return Number(Math.min(max, Math.max(min, gerundet)).toFixed(2));
}

export function oderVorgabe(wert: number | undefined, bereich: Bereich): number {
  return wert && wert >= bereich.min && wert <= bereich.max ? wert : bereich.vorgabe;
}
