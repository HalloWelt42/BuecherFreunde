// Der Lesestand eines Buchs im Kinderleser, in denselben Formen wie beim normalen Leser (pdf:, epub:, txt:), damit Einblick der
// Eltern, Weiterlesen und ein späterer Wechsel in den normalen Leser ihn verstehen. Dazu im Feld "kind" die genaue Stelle und das
// eine Lesezeichen. Ob ein Buch fertig gelesen ist, entscheidet der Server nach seiner Regel (fertig_am am Buch).
import { lesestand, lesewerte, type Lesewerte } from "../lesestand";
import type { Buch } from "../typen";
import type { Kinderstelle } from "./typen";

/** Ab diesem Anteil steht der Lesestand am Ende (wie lesestand.fertig_ab in stufen.json); dann beginnt das Buch neu */
export const FERTIG_AB = 0.99;

/** Zum Weiterlesen: das Buch, in dem zuletzt gelesen wurde und dessen Lesestand noch nicht am Ende steht; sonst keins */
export function weiterzulesen(buecher: readonly Buch[]): Buch | null {
  const offen = buecher.filter((b) => {
    const s = lesestand(b);
    return s.angefangen && s.anteil < FERTIG_AB;
  });
  return offen.toSorted((a, b) => (b.last_read_at ?? "").localeCompare(a.last_read_at ?? ""))[0] ?? null;
}

export interface Kindangaben {
  einheit: number;
  zeichen: number;
  lesezeichen: Kinderstelle | null;
}

export type Kinderlesewerte = Lesewerte & { kind?: Kindangaben };

const stelleOk = (s: unknown): s is Kinderstelle =>
  !!s && typeof s === "object" && Number.isInteger((s as Kinderstelle).einheit) && Number.isInteger((s as Kinderstelle).zeichen) && (s as Kinderstelle).einheit >= 0 && (s as Kinderstelle).zeichen >= 0;

/** Die Angaben des Kinderlesers aus einem gemerkten Stand; null, wenn er von woanders kommt */
export function kindangabenAus(position: string | null | undefined): Kindangaben | null {
  const k = (lesewerte(position) as Kinderlesewerte).kind;
  if (!k || !stelleOk(k)) return null;
  return { einheit: k.einheit, zeichen: k.zeichen, lesezeichen: stelleOk(k.lesezeichen) ? k.lesezeichen : null };
}

export function kinderlesewerte(grund: Lesewerte, stelle: Kinderstelle, lesezeichen: Kinderstelle | null): Kinderlesewerte {
  return { ...grund, kind: { einheit: stelle.einheit, zeichen: stelle.zeichen, lesezeichen } };
}
