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
