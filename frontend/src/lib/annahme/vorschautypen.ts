// Die Vorschau vor dem Übernehmen (BF-80), so wie der Server sie zeigt (docs/neubau/SCHNITTSTELLE.md, Hochladen mit Vorschau)
import type { Annahmestand, Vorschaukurz } from "./typen";

/** Woher ein Vorschlag kommt; "nutzer" überschreibt danach weder Regel noch KI */
export type Herkunft = "regel" | "ki" | "ordner" | "datei" | "luecke" | "bestand" | "nutzer";

export interface Wert<T> {
  wert: T;
  /** leer: noch kein Vorschlag */
  herkunft: Herkunft | null;
  grund: string;
}

export type Doppelart = "neu" | "gleich" | "format";
export type Doppelwahl = "neu" | "weglassen" | "format" | "eigenes";

export interface Doppel {
  art: Doppelart;
  wahl: Doppelwahl;
  herkunft: Herkunft | null;
  /** etwa "gleiche Datei im Bestand" oder "zu Sturmflut, EPUB" */
  grund: string;
}

/** Zu welchem Buch eine Datei als weiteres Format oder Material gehört: eins im Bestand oder eine Aufnahme dieser Vorschau */
export interface Ziel {
  buch_id: number | null;
  aufnahme: number | null;
  titel: string;
}

/** Art in der Vorschau: "buch", eine Art unter Besonderes, "material"; leer heißt noch offen */
export type Vorschauart = "" | "buch" | "dokument" | "heft" | "katalog" | "broschuere" | "anleitung" | "material";

export interface Hinweis {
  text: string;
  herkunft: Herkunft | null;
}

export interface Zuordnung {
  art: Wert<string>;
  gattung: string | null;
  kategorien: Wert<number[]>;
  etiketten: Wert<string[]>;
  sammlung: Wert<number | null>;
  band: Wert<string>;
  sprache: Wert<string>;
  doppel: Doppel;
  ziel: Ziel | null;
  /** warum nicht übernommen; leer: wird übernommen */
  nicht: string;
  /** kurze Sätze und woher sie kommen, etwa "Die Datei ist englisch, die Lücke deutsch" (luecke, BF-75) */
  hinweise: Hinweis[];
  bestaetigt: boolean;
  von_profil: string | null;
}

export interface Gelesen {
  titel: string;
  autor: string;
  isbn: string;
  verlag: string;
  jahr: number | null;
  sprache: string;
  beschreibung: string;
  seiten: number;
  umschlag: boolean;
  umschlag_schlicht: boolean | null;
}

export interface Ablageziel {
  /** bleibt: im Eingang oder im Ordner, wo sie liegt */
  ort: "kellerwolke" | "geraet" | "bleibt";
  ordner: string;
  name: string;
}

export type Rolle = "buch" | "material" | "zip" | "doppel" | "rest";

export interface Vorschauzeile {
  id: number;
  name: string;
  groesse: number;
  /** Ordner in der ZIP, nur als Hinweis */
  ordner: string;
  stand: Annahmestand;
  text: string;
  rolle: Rolle;
  buch_id: number | null;
  /** Es gibt ein Bild unter GET /api/annahme/{id}/umschlag */
  umschlag: boolean;
  /** offen: die KI prüft noch */
  ki: "" | "offen" | "fertig";
  /** So viele Dateien dieser Vorschau kommen als Begleitmaterial zu ihr */
  material: number;
  gelesen: Gelesen | null;
  felder: Zuordnung | null;
  ablage: Ablageziel | null;
}

export interface Vorschauzaehler {
  gesamt: number;
  uebernehmen: number;
  buecher: number;
  besonderes: number;
  material: number;
  formate: number;
  weglassen: number;
  nicht: number;
  offen: number;
  laeuft: number;
  ki: number;
}

export interface Vorgabe {
  sammlung_id: number | null;
  band: string;
  sprache: string;
}

export interface Vorschau extends Vorschaukurz {
  vorgabe: Vorgabe;
  zaehler: Vorschauzaehler;
  zeilen: Vorschauzeile[];
}

/** Was ein PATCH setzt; ein genanntes Feld gilt für alle genannten Dateien und heißt danach "nutzer" */
export interface Felderaenderung {
  art?: Vorschauart;
  kategorien?: number[];
  etiketten?: string[];
  /** null leert */
  sammlung?: number | null;
  band?: string;
  sprache?: string;
  doppel?: Doppelwahl;
  /** null leert */
  ziel?: { buch_id: number } | { aufnahme: number } | null;
}

export type Verwerfwirkung = "papierkorb" | "endgueltig" | "bleibt" | "nichts";

export interface Verwerffolgen {
  vorschau: string;
  name: string;
  dateien: { id: number; name: string; ordner: string; groesse: number; wirkung: Verwerfwirkung; pfad: string }[];
  papierkorb: number;
  endgueltig: number;
  bleibt: number;
  /** Ohne ihn verwirft der Server nicht; hat sich seither etwas geändert, antwortet er 409 */
  stand: string;
}

export interface Hinzufuegeeinstellungen {
  bestaetigen: { hochladen: true; eingangsordner: boolean; ordner: boolean };
  zip: { dateien: number; datei_mb: number; gesamt_mb: number; tiefe: number; verhaeltnis: number };
}
