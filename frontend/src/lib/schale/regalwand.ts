// Regalwand als fertiges Bild: Buchrücken in den Farben der eigenen Umschläge, einmal gezeichnet
import type { Dreiklang } from "../farben";

const B = 1200;
const H = 760;
const BRETT = 190;

/** Wiederholbarer Zufall: dieselbe Wand bei denselben Farben */
function wuerfel(saat: number): () => number {
  let s = saat;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

function ruecken(g: CanvasRenderingContext2D, x: number, boden: number, b: number, h: number, farbe: string, schmuck: string): void {
  g.fillStyle = farbe;
  g.fillRect(x, boden - h, b, h);
  const rundung = g.createLinearGradient(x, 0, x + b, 0);
  rundung.addColorStop(0, "rgba(0,0,0,.45)");
  rundung.addColorStop(0.3, "rgba(255,255,255,.22)");
  rundung.addColorStop(1, "rgba(0,0,0,.5)");
  g.fillStyle = rundung;
  g.fillRect(x, boden - h, b, h);
  g.fillStyle = schmuck;
  g.globalAlpha = 0.75;
  g.fillRect(x + 3, boden - h + 16, b - 6, 4);
  g.fillRect(x + 3, boden - 22, b - 6, 3);
  if (b > 24) g.fillRect(x + b / 2 - 2, boden - h + 34, 4, h * 0.36);
  g.globalAlpha = 1;
}

function brett(g: CanvasRenderingContext2D, y0: number, boden: number): void {
  g.fillStyle = "#5b4330";
  g.fillRect(0, boden, B, 12);
  g.fillStyle = "rgba(255,255,255,.16)";
  g.fillRect(0, boden, B, 2);
  const schatten = g.createLinearGradient(0, y0, 0, y0 + 60);
  schatten.addColorStop(0, "rgba(0,0,0,.6)");
  schatten.addColorStop(1, "transparent");
  g.fillStyle = schatten;
  g.fillRect(0, y0, B, 60);
}

export function zeichneRegalwand(flaeche: HTMLCanvasElement, farben: Dreiklang[]): void {
  flaeche.width = B;
  flaeche.height = H;
  const g = flaeche.getContext("2d");
  if (!g || !farben.length) return;
  const z = wuerfel(7);
  g.fillStyle = "#2a2019";
  g.fillRect(0, 0, B, H);
  for (let r = 0; r * BRETT < H; r++) {
    const y0 = r * BRETT;
    const boden = y0 + 178;
    let x = 4;
    while (x < B) {
      const f = farben[Math.floor(z() * farben.length)];
      const b = 14 + z() * 30;
      const h = 112 + z() * 54;
      ruecken(g, x, boden, b, h, f[Math.floor(z() * 2.4)], f[2]);
      x += b + 1.5 + (z() > 0.93 ? 22 : 0);
    }
    brett(g, y0, boden);
  }
}

/** Eigenes Bild: klein gezeichnet und vom Browser hochgezogen, so ist es weich, ohne dass jedes Bild neu rechnet. */
export function zeichneBild(flaeche: HTMLCanvasElement, bild: HTMLImageElement): void {
  flaeche.width = 480;
  flaeche.height = 304;
  const g = flaeche.getContext("2d");
  if (!g || !bild.naturalWidth) return;
  const mass = Math.max(flaeche.width / bild.naturalWidth, flaeche.height / bild.naturalHeight);
  const b = bild.naturalWidth * mass;
  const h = bild.naturalHeight * mass;
  g.imageSmoothingQuality = "high";
  g.drawImage(bild, (flaeche.width - b) / 2, (flaeche.height - h) / 2, b, h);
}
