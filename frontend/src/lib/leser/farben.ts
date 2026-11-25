// Farben zum Markieren und Benennen
export interface Stiftfarbe {
  farbe: string;
  name: string;
}

export const STIFTFARBEN: Stiftfarbe[] = [
  { farbe: "#FFEE58", name: "Gelb" }, { farbe: "#FFA726", name: "Orange" }, { farbe: "#FF7043", name: "Tiefes Orange" }, { farbe: "#EF5350", name: "Rot" },
  { farbe: "#EC407A", name: "Pink" }, { farbe: "#AB47BC", name: "Lila" }, { farbe: "#7E57C2", name: "Violett" }, { farbe: "#5C6BC0", name: "Indigo" },
  { farbe: "#42A5F5", name: "Blau" }, { farbe: "#4FC3F7", name: "Hellblau" }, { farbe: "#26C6DA", name: "Cyan" }, { farbe: "#26A69A", name: "Petrol" },
  { farbe: "#66BB6A", name: "Grün" }, { farbe: "#9CCC65", name: "Hellgrün" }, { farbe: "#8D6E63", name: "Braun" }, { farbe: "#BDBDBD", name: "Grau" },
];

export const VORGABE_STIFT = "#FFEE58";
export const VORGABE_ETIKETT = "#4FC3F7";

export function durchsichtig(hex: string, deckung: number): string {
  const n = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => Number.parseInt(n.slice(i, i + 2), 16) || 0);
  return `rgba(${r}, ${g}, ${b}, ${deckung})`;
}
