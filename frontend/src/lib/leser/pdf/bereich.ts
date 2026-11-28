// Ein Rechteck auf einer PDF-Seite als Stelle einer Markierung (BF-123): page:N:bereich:x0,y0,x1,y1, die Ecken in Anteilen der
// Seite mit vier Stellen. Dasselbe Format liest und schreibt der Server (backend/app/markierungen/stelle.py). Der Anfang page:N
// ist der von Markierungen im Text, so nennen Liste, Randmarken und Sprünge die Seite wie immer.

/** Ein Rechteck in Anteilen der Seite, links oben (x0, y0) bis rechts unten (x1, y1) */
export interface Bereich {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/** So groß (Anteil der Seite, je Richtung) muss ein gezogenes Rechteck mindestens sein; kleiner ist es ein Klick */
export const MINDESTENS = 0.01;
const MUSTER = /^page:(\d+):bereich:(\d(?:\.\d+)?),(\d(?:\.\d+)?),(\d(?:\.\d+)?),(\d(?:\.\d+)?)$/;

const vier = (n: number) => n.toFixed(4);

export function stelleVon(seite: number, b: Bereich): string {
  return `page:${seite}:bereich:${vier(b.x0)},${vier(b.y0)},${vier(b.x1)},${vier(b.y1)}`;
}

/** Seite und Rechteck einer Stelle; null, wenn sie kein gültiges Rechteck nennt */
export function bereichAus(stelle: string): { seite: number; bereich: Bereich } | null {
  const m = MUSTER.exec(stelle);
  if (!m) return null;
  const [seite, x0, y0, x1, y1] = m.slice(1).map(Number);
  if (seite < 1 || [x0, y0, x1, y1].some((n) => n > 1) || x1 <= x0 || y1 <= y0) return null;
  return { seite, bereich: { x0, y0, x1, y1 } };
}

const klemme = (n: number) => Math.min(1, Math.max(0, n));

/** Das Rechteck zwischen zwei Punkten (im Fenster) auf einer Seite (ihr Rahmen im Fenster); null, wenn es zu klein ist */
export function bereichZwischen(seite: { left: number; top: number; width: number; height: number }, a: { x: number; y: number }, b: { x: number; y: number }): Bereich | null {
  if (!seite.width || !seite.height) return null;
  const x = [a.x, b.x].map((v) => klemme((v - seite.left) / seite.width)).sort((p, q) => p - q);
  const y = [a.y, b.y].map((v) => klemme((v - seite.top) / seite.height)).sort((p, q) => p - q);
  if (x[1] - x[0] < MINDESTENS || y[1] - y[0] < MINDESTENS) return null;
  return { x0: x[0], y0: y[0], x1: x[1], y1: y[1] };
}

const prozent = (n: number) => `${Math.round(n * 1e6) / 1e4}%`;

/** Lage im Rahmen der Seite in Prozent, für ein Element darin */
export const alsLage = (b: Bereich) => ({ left: prozent(b.x0), top: prozent(b.y0), width: prozent(b.x1 - b.x0), height: prozent(b.y1 - b.y0) });
