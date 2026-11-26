// Der Lesestand eines Buchs im Kinderleser, in denselben Formen wie beim normalen Leser (pdf:, epub:, txt:), damit Einblick der
// Eltern, Weiterlesen und ein späterer Wechsel in den normalen Leser ihn verstehen. Dazu im Feld "kind" die genaue Stelle, das
// eine Lesezeichen und ob das Buch zu Ende gelesen ist.
import { lesewerte, type Lesewerte } from "../lesestand";
import type { Kinderstelle } from "./typen";

export interface Kindangaben {
  einheit: number;
  zeichen: number;
  lesezeichen: Kinderstelle | null;
  fertig: boolean;
}

export type Kinderlesewerte = Lesewerte & { kind?: Kindangaben };

const stelleOk = (s: unknown): s is Kinderstelle =>
  !!s && typeof s === "object" && Number.isInteger((s as Kinderstelle).einheit) && Number.isInteger((s as Kinderstelle).zeichen) && (s as Kinderstelle).einheit >= 0 && (s as Kinderstelle).zeichen >= 0;

/** Die Angaben des Kinderlesers aus einem gemerkten Stand; null, wenn er von woanders kommt */
export function kindangabenAus(position: string | null | undefined): Kindangaben | null {
  const k = (lesewerte(position) as Kinderlesewerte).kind;
  if (!k || !stelleOk(k)) return null;
  return { einheit: k.einheit, zeichen: k.zeichen, lesezeichen: stelleOk(k.lesezeichen) ? k.lesezeichen : null, fertig: k.fertig === true };
}

/** Zu Ende gelesen? Im Kinderleser so gemerkt, sonst nach dem Anteil */
export function fertigGelesen(position: string | null | undefined, seiten = 0): boolean {
  const k = kindangabenAus(position);
  if (k) return k.fertig;
  const w = lesewerte(position);
  if (w.page && seiten) return w.page >= seiten;
  return (w.percent ?? w.scrollPct ?? 0) >= 99;
}

export function kinderlesewerte(grund: Lesewerte, stelle: Kinderstelle, lesezeichen: Kinderstelle | null, fertig: boolean): Kinderlesewerte {
  return { ...grund, kind: { einheit: stelle.einheit, zeichen: stelle.zeichen, lesezeichen, fertig } };
}
