// Der Lesestand eines Buchs im Kinderleser, in denselben Formen wie beim normalen Leser (pdf:, epub:, txt:), damit Einblick der
// Eltern, Weiterlesen und ein späterer Wechsel in den normalen Leser ihn verstehen. Dazu im Feld "kind" die genaue Stelle und das
// eine Lesezeichen. Ob ein Buch fertig gelesen ist, entscheidet der Server nach seiner Regel (fertig_am am Buch).
import { lesewerte, type Lesewerte } from "../lesestand";
import type { Kinderstelle } from "./typen";

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
