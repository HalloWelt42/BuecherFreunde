// Reihenfolge der Bände beim Ziehen (BF-67): rein, ohne Oberfläche, damit sie sich prüfen lässt
import type { Buch } from "../../lib/typen";

/** Die gezogenen Nummern stehen danach zusammen vor `vor` (null: am Ende), in der Reihenfolge, in der sie gezogen wurden.
 *  Neue (noch nicht in der Liste) kommen so hinein. Liegt `vor` selbst unter den gezogenen, gilt der nächste nicht gezogene. */
export function ordne(liste: number[], gezogen: number[], vor: number | null): number[] {
  const weg = new Set(gezogen);
  let anker = vor;
  if (anker !== null && weg.has(anker)) {
    const ab = liste.indexOf(anker);
    anker = liste.slice(ab + 1).find((id) => !weg.has(id)) ?? null;
  }
  const rest = liste.filter((id) => !weg.has(id));
  const stelle = anker === null ? rest.length : rest.indexOf(anker);
  const an = stelle < 0 ? rest.length : stelle;
  return [...rest.slice(0, an), ...new Set(gezogen), ...rest.slice(an)];
}

/** Gleich geblieben? Dann muss nichts an den Server */
export function gleich(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((x, n) => x === b[n]);
}

/** Tragen die Bände schon genau die Nummern 1 bis n in dieser Reihenfolge? Sonst gehen beim Durchzählen Nummern verloren
 *  (Lücken, Buchstaben, doppelte), und das braucht eine Rückfrage. */
export function vergibtNeu(liste: Pick<Buch, "band_nummer">[]): boolean {
  return !liste.every((b, n) => (b.band_nummer ?? "").trim() === String(n + 1));
}

/** Was das Durchzählen ändert: je Buch, dessen Nummer anders wird, alt und neu */
export function neueNummern(buecher: Pick<Buch, "id" | "title" | "band_nummer">[], reihenfolge: number[]): { titel: string; alt: string; neu: string }[] {
  const nach = new Map(buecher.map((b) => [b.id, b]));
  return reihenfolge.flatMap((id, n) => {
    const b = nach.get(id);
    const alt = (b?.band_nummer ?? "").trim();
    return b && alt !== String(n + 1) ? [{ titel: b.title, alt, neu: String(n + 1) }] : [];
  });
}
