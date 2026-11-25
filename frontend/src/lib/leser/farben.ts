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

export interface Hsl {
  h: number;
  s: number;
  l: number;
}

export function hexZuHsl(hex: string): Hsl {
  const n = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => (Number.parseInt(n.slice(i, i + 2), 16) || 0) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  const l = (max + min) / 2;
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  const h = d === 0 ? 0 : max === r ? ((g - b) / d + 6) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return { h: Math.round(h * 60), s: Math.round(s * 100), l: Math.round(l * 100) };
}

export function hslZuHex({ h, s, l }: Hsl): string {
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const teil = (n: number) => {
    const k = (n + h / 30) % 12;
    return Math.round(255 * (l / 100 - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))));
  };
  return `#${[teil(0), teil(8), teil(4)].map((w) => w.toString(16).padStart(2, "0")).join("")}`;
}
