// Bücher: Liste, Einzelnes, Umschlag, Datei, Text
import { anfrage, del, get, patch, post, put } from "./client";
import type { Parameter } from "./client";
import type { Buch, BuchEinzeln, BuchListe, Loeschfolgen } from "../typen";

export interface Buchtreffer {
  seite: number;
  kontext: string;
  position: number;
  prozent: number;
}

export interface Suchschalter {
  limit?: number;
  ganzes_wort?: boolean;
  gross_klein?: boolean;
  regex?: boolean;
}

export const listeBooks = (params: Parameter): Promise<BuchListe> => get("/api/books", params);
export const holeBuch = (id: number): Promise<BuchEinzeln> => get(`/api/books/${id}`);
export const aehnlicheBuecher = (id: number): Promise<{ vom_autor: Buch[]; in_kategorie: Buch[] }> => get(`/api/books/${id}/aehnliche`);
export const loeschfolgen = (id: number): Promise<Loeschfolgen> => get(`/api/books/${id}/loeschfolgen`);
export const loescheBuch = (id: number): Promise<{ geloescht: boolean; id: number }> => del(`/api/books/${id}`);
export const aktualisiereBuch = (id: number, daten: Record<string, unknown>): Promise<BuchEinzeln> => patch(`/api/books/${id}`, daten);
/** Nur das aktive Profil sieht das Buch (BF-78) */
export const setzePrivat = (id: number, privat: boolean): Promise<{ privat: boolean }> => put(`/api/books/${id}/privat`, { privat });
/** Was POST /api/books/bulk mit mehreren Büchern tut; wert ist je nach Aktion Regal, Sammlung, Art oder ein Schalter */
export type Sammelaktion = "loeschen" | "favorit" | "zu_lesen" | "typ_setzen" | "kategorie_zuweisen" | "kategorie_entfernen" | "sammlung_zuweisen" | "sammlung_entfernen";

export const bulkAction = (buecher: number[], aktion: Sammelaktion, wert: unknown): Promise<{ betroffen: number }> => post("/api/books/bulk", { book_ids: buecher, aktion, wert });
export const umschlagNeu = (id: number): Promise<any> => post(`/api/books/${id}/cover/neu-extrahieren`);
export const isbnScan = (id: number): Promise<Isbnsuche> => post(`/api/books/${id}/isbn-scan`);
/** Eine ISBN bei den Quellen, der Reihe nach bis zum ersten Fund, und ihre Stufe gegen Titel und Autor (BF-111) */
export const isbnPruefen = (id: number, isbn: string): Promise<Isbnpruefung> => post(`/api/books/${id}/isbn-pruefen`, { isbn });
/** ISBN zur Wahl aus dem Lauf "ISBN" für dieses Buch, in der Rangfolge */
export const isbnZurWahl = (id: number): Promise<Isbnkandidat[]> => get(`/api/books/${id}/isbn-wahl`);

/** Das Deckblatt aus der Datei, noch nicht gespeichert (BF-112); 422, wenn die Datei keines hat */
export async function umschlagAusDatei(id: number): Promise<Blob> {
  return (await anfrage(`/api/books/${id}/cover/aus-datei`)).blob();
}

/** Wie gut eine ISBN zu Titel und Autor passt, vom besten zum schlechtesten */
export type Stufe = "passt" | "aehnlich" | "unbekannt" | "fremd";
/** Wo im Buch eine ISBN steht; so auch die Rangfolge */
export type Fundort = "impressum" | "rueckseite" | "titelei" | "text" | "anmerkungen" | "verlagsanzeige" | "literaturliste";
/** Was der Text neben der Nummer über die Ausgabe sagt; leer: nichts */
export type Ausgabe = "druck" | "ebook" | "";

export interface Fundstelle {
  /** Dateiseite ab 1, wie im Leser */
  seite: number;
  /** Lage im Buch, für Formate ohne Seiten */
  prozent: number;
  fundort: Fundort;
  /** maskiert, die Nummer in <mark> (wie in der Suche im Buch) */
  ausschnitt: string;
  funde: number;
}

export interface Einstufung {
  stufe: Stufe;
  /** Kennung der Quelle; leer: aus dem Text */
  quelle: string;
  /** "im Text" oder der Name der Quelle */
  basis: string;
  /** maskiert, Abweichendes in <mark> */
  was: string;
  warum: string;
}

export interface Isbnkandidat {
  /** ISBN-13 mit Strichen */
  isbn: string;
  isbn13: string;
  /** wie sie sonst im Buch steht */
  formen: string[];
  ausgabe: Ausgabe;
  funde: number;
  fundort: Fundort;
  stellen: Fundstelle[];
  text: Einstufung;
  quelle: Einstufung | null;
}

export interface Isbnsuche {
  kandidaten: Isbnkandidat[];
  funde: number;
  aktuell: string;
  /** Seiten des durchsuchten Texts; 0: das Buch hat keinen */
  seiten: number;
}

export interface Isbnpruefung {
  isbn: string;
  /** null: keine gefragte Quelle kennt sie */
  einstufung: Einstufung | null;
  hinweise: string[];
  ruht: boolean;
}
export const textSeiten = (id: number, ab: number, anzahl: number): Promise<any> => get(`/api/books/${id}/textseiten`, { ab, anzahl });

/** Antwort der Texterkennung auf die Bitte um Vorrang (BF-109): bereit oder nicht (mit Grund), und welche Seiten von `von` bis
 *  `bis` noch auf ihre Erkennung warten */
export interface Vorrangstand {
  bereit: boolean;
  grund: string;
  von: number;
  bis: number;
  wartet: number[];
}

/** Hier wird gelesen: diese Seite und die nächsten zuerst erkennen; wiederholt ist es das Nachfragen */
export const texterkennungVorrang = (id: number, seite: number): Promise<Vorrangstand> => post(`/api/books/${id}/texterkennung/vorrang`, { seite });

export function textBildUrl(id: number, seite: number, nr: number): string {
  return `/api/books/${id}/textseiten/${seite}/bild/${nr}`;
}

/** `stand` ändert sich mit dem Bild (cover_stand), sonst mit dem Buch. */
export function coverUrl(id: number, stand?: string | number): string {
  return `/api/books/${id}/cover${stand ? `?_v=${encodeURIComponent(stand)}` : ""}`;
}

/** Die Datei zum Ansehen: der Server schickt sie inline (Im Browser, Leser) */
export function dateiUrl(id: number): string {
  return `/api/books/${id}/file`;
}

/** Dieselbe Adresse zum Herunterladen: der Server schickt die Datei als Anhang */
export function alsAnhang(adresse: string): string {
  return `${adresse}${adresse.includes("?") ? "&" : "?"}herunterladen=true`;
}

export const ladeUrl = (id: number): string => alsAnhang(dateiUrl(id));

export function volltextSuche(id: number, wort: string, schalter: Suchschalter = {}): Promise<{ treffer: Buchtreffer[]; gesamt: number; seiten_gesamt?: number }> {
  const { limit = 500, ganzes_wort, gross_klein, regex } = schalter;
  return get(`/api/books/${id}/volltext-suche`, { q: wort, limit, ganzes_wort: ganzes_wort || undefined, gross_klein: gross_klein || undefined, regex: regex || undefined });
}
