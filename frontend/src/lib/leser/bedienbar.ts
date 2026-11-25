// Ist das etwas zum Bedienen? Dann gehört ihm das Tippen. Ohne instanceof: im Buchrahmen sind es Elemente eines anderen Fensters.
const BEDIENBAR = "a[href], button, input, select, textarea, label, summary, audio, video, [role='button'], [contenteditable='true']";

export function istBedienbar(ziel: EventTarget | null): boolean {
  const knoten = ziel as (Node & { closest?: (s: string) => Element | null }) | null;
  const element = knoten?.closest ? knoten : (knoten?.parentElement ?? null);
  return !!element?.closest?.(BEDIENBAR);
}
