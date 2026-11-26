// Das gestaltete Deckblatt eines Buchs (BF-59): reine Funktion von Nummer, Titel, Autor, Jahr, Art und Gattung zum SVG.
// Alles aus den Daten wird maskiert; das Blatt nutzt keine Kennungen (id), mehrere auf einer Seite stören sich nicht.
import type { Dreiklang } from "../farben";
import { MUSTER, type Blatt, type Mustername } from "./muster";
import { gekuerzt, H } from "./satz";
import { farbsatz, gestaltFuer, type Form } from "./zuordnung";

export interface Blattangaben {
  id: number;
  title: string;
  author?: string;
  year?: number | null;
  typ?: string;
  gattung?: string;
}

/** Längere Titel enden mit " ..."; so bleibt die Schrift auf dem Blatt lesbar */
const TITEL_HOECHSTENS = 80;

/** Welches Muster in welchen Farben und welcher Form ein Buch bekommt */
export function gestaltung(buch: Blattangaben): { muster: Mustername; farben: Dreiklang; form: Form } {
  const gestalt = gestaltFuer(buch.typ, buch.gattung);
  return { muster: gestalt.muster, farben: farbsatz(gestalt, buch.id), form: gestalt.form ?? "buch" };
}

/** Die drei Farben des Blatts, für Licht und Regalwand */
export const blattFarben = (buch: Blattangaben): Dreiklang => gestaltung(buch).farben;

function blatt(buch: Blattangaben): Blatt {
  const titel = (buch.title ?? "").trim().replace(/\s+/g, " ");
  return { titel: gekuerzt(titel || "Ohne Titel", TITEL_HOECHSTENS), autor: (buch.author ?? "").trim().replace(/\s+/g, " "), jahr: buch.year ? String(buch.year) : "" };
}

/** Das Blatt als SVG, 200 breit und 300 hoch; data-form sagt dem Rahmen (.umschlag), ob es als Buch oder Ordner steht */
export function gestaltetesBlatt(buch: Blattangaben): string {
  const { muster, farben, form } = gestaltung(buch);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 ${H}" data-form="${form}" aria-hidden="true">${MUSTER[muster](blatt(buch), farben)}</svg>`;
}
