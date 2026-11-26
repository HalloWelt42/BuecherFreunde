// Farben als Farbton, Sättigung, Helligkeit: für die Regler der Farbwahl

export interface Farbton {
  /** 0 bis 360 */
  ton: number;
  /** 0 bis 100 */
  saettigung: number;
  /** 0 bis 100 */
  helligkeit: number;
}

/** "#abc", "abc123" und "#ABC123" werden zu "#aabbcc"; alles andere ist keine Farbe. */
export function alsHex(eingabe: string): string | null {
  const roh = eingabe.trim().replace(/^#/, "").toLowerCase();
  if (/^[0-9a-f]{3}$/.test(roh)) return `#${[...roh].map((z) => z + z).join("")}`;
  return /^[0-9a-f]{6}$/.test(roh) ? `#${roh}` : null;
}

export function hexZuTon(farbe: string): Farbton {
  const hex = alsHex(farbe) ?? "#808080";
  const [r, g, b] = [1, 3, 5].map((n) => Number.parseInt(hex.slice(n, n + 2), 16) / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const weite = max - min;
  const mitte = (max + min) / 2;
  if (!weite) return { ton: 0, saettigung: 0, helligkeit: Math.round(mitte * 100) };
  const anteil = max === r ? ((g - b) / weite + 6) % 6 : max === g ? (b - r) / weite + 2 : (r - g) / weite + 4;
  return { ton: Math.round(anteil * 60), saettigung: Math.round((weite / (1 - Math.abs(2 * mitte - 1))) * 100), helligkeit: Math.round(mitte * 100) };
}

export function tonZuHex({ ton, saettigung, helligkeit }: Farbton): string {
  const s = saettigung / 100;
  const h = helligkeit / 100;
  const a = s * Math.min(h, 1 - h);
  const kanal = (n: number) => {
    const k = (n + ton / 30) % 12;
    return Math.round(255 * (h - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)))).toString(16).padStart(2, "0");
  };
  return `#${kanal(0)}${kanal(8)}${kanal(4)}`;
}

// Kontrast nach WCAG und die Zeichenfläche des Katalogs (BF-69)

/** Das Zeichen steht hell auf seiner Fläche */
export const ZEICHENFARBE = "#ffffff";
/** Ziel mit Luft zu den geforderten 4,5 : 1, damit Runden nie darunter fällt */
const ZIEL_KONTRAST = 5;
/** Jede Fläche ist mindestens so weit mit Schwarz gemischt (Anteil der Farbe in Oklab), auch dunkle: ruhiger und weniger bunt */
const HOECHSTENS_FARBE = 0.85;

const linear = (k: number) => (k <= 0.04045 ? k / 12.92 : ((k + 0.055) / 1.055) ** 2.4);
const gamma = (k: number) => (k <= 0.0031308 ? 12.92 * k : 1.055 * k ** (1 / 2.4) - 0.055);

function kanaele(farbe: string): [number, number, number] {
  const hex = alsHex(farbe) ?? "#808080";
  return [1, 3, 5].map((n) => linear(Number.parseInt(hex.slice(n, n + 2), 16) / 255)) as [number, number, number];
}

/** Relative Leuchtdichte, 0 (schwarz) bis 1 (weiß) */
export function leuchtdichte(farbe: string): number {
  const [r, g, b] = kanaele(farbe);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function kontrast(a: string, b: string): number {
  const [hell, dunkel] = [leuchtdichte(a), leuchtdichte(b)].sort((x, y) => y - x);
  return (hell + 0.05) / (dunkel + 0.05);
}

/**
 * Fläche für ein Zeichen in dieser Farbe: die Farbe in Oklab mit Schwarz gemischt, so weit, dass das helle Zeichen darauf
 * mindestens 5 : 1 erreicht, und nie weniger als 15 %. Eine Mischung mit Schwarz in Oklab mit dem Anteil t ist dasselbe
 * wie die linearen Kanäle mal t³; der Farbton bleibt also genau, nur die Helligkeit fällt.
 */
export function zeichenflaeche(farbe: string, zeichen = ZEICHENFARBE): string {
  const [r, g, b] = kanaele(farbe);
  const l = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const hoechstens = (leuchtdichte(zeichen) + 0.05) / ZIEL_KONTRAST - 0.05;
  const faktor = Math.min(HOECHSTENS_FARBE ** 3, l > 0 ? hoechstens / l : 1);
  const kanal = (k: number) => Math.round(Math.min(1, Math.max(0, gamma(k * faktor))) * 255).toString(16).padStart(2, "0");
  return `#${kanal(r)}${kanal(g)}${kanal(b)}`;
}
