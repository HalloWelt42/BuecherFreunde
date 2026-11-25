// Farben aus einem Umschlag: die drei kräftigsten, weit auseinanderliegenden Töne. Speist Regalwand und Lichtkulisse.

export type Dreiklang = [string, string, string];

const SEITE = 24;

interface Korb {
  r: number;
  g: number;
  b: number;
  n: number;
}

export function hex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map((w) => Math.round(w).toString(16).padStart(2, "0")).join("")}`;
}

function kraft(k: Korb): number {
  const max = Math.max(k.r, k.g, k.b) / k.n;
  const min = Math.min(k.r, k.g, k.b) / k.n;
  return k.n * (0.35 + (max - min) / 255);
}

function abstand(a: Korb, b: Korb): number {
  return Math.abs(a.r / a.n - b.r / b.n) + Math.abs(a.g / a.n - b.g / b.n) + Math.abs(a.b / a.n - b.b / b.n);
}

/** Bildpunkte (rgba, hintereinander) zu drei Farben; leere oder durchsichtige Bilder ergeben null. */
export function dreiklang(punkte: Uint8ClampedArray): Dreiklang | null {
  const koerbe = new Map<number, Korb>();
  for (let i = 0; i < punkte.length; i += 4) {
    if (punkte[i + 3] < 128) continue;
    const [r, g, b] = [punkte[i], punkte[i + 1], punkte[i + 2]];
    const schluessel = ((r >> 5) << 6) | ((g >> 5) << 3) | (b >> 5);
    const korb = koerbe.get(schluessel) ?? { r: 0, g: 0, b: 0, n: 0 };
    korb.r += r;
    korb.g += g;
    korb.b += b;
    korb.n += 1;
    koerbe.set(schluessel, korb);
  }
  const sortiert = [...koerbe.values()].sort((a, b) => kraft(b) - kraft(a));
  if (!sortiert.length) return null;
  const wahl: Korb[] = [sortiert[0]];
  for (const grenze of [140, 70, 0]) {
    for (const k of sortiert) {
      if (wahl.length === 3) break;
      if (!wahl.includes(k) && wahl.every((w) => abstand(w, k) >= grenze)) wahl.push(k);
    }
  }
  while (wahl.length < 3) wahl.push(wahl[0]);
  return wahl.map((k) => hex(k.r / k.n, k.g / k.n, k.b / k.n)) as Dreiklang;
}

/** Farben eines geladenen Bilds derselben Adresse; null, wenn der Browser nicht zeichnen kann. */
export function farbenAusBild(bild: HTMLImageElement): Dreiklang | null {
  try {
    const flaeche = document.createElement("canvas");
    flaeche.width = SEITE;
    flaeche.height = SEITE;
    const stift = flaeche.getContext("2d", { willReadFrequently: true });
    if (!stift || !bild.naturalWidth) return null;
    stift.drawImage(bild, 0, 0, SEITE, SEITE);
    return dreiklang(stift.getImageData(0, 0, SEITE, SEITE).data);
  } catch {
    return null;
  }
}
