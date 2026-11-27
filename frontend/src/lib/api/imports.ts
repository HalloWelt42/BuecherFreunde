// Einlesen von Ordnern und Ergänzen der Bibliothek; Stand und Fortschritt des Einlesens führt die Annahme (/api/annahme)
import type { Buch } from "../typen";
import type { Isbnkandidat } from "./books";
import { get, post } from "./client";

export type Ergaenzungsart = "cover" | "isbn" | "metadaten" | "volltext";

export interface Einlesestart {
  gefunden: number;
  neu: number;
}

export interface Einlesedatei {
  name: string;
  pfad: string;
  groesse: number;
  format: string;
  ist_duplikat: boolean;
  bestehendes_buch: string | null;
}

export interface Einlesevorschau {
  dateien: Einlesedatei[];
  verzeichnis: string;
  gesamt?: number;
  neu?: number;
  duplikate?: number;
}

export interface Ergaenzungsvorschau {
  gesamt: number;
  typen: Partial<Record<Ergaenzungsart, number>>;
}

export interface Ergaenzungsregal {
  id: number | null;
  name: string;
  anzahl: number;
}

export const scanneImportVerzeichnis = (anreichern = false): Promise<Einlesestart> => post(`/api/import/scan?anreichern=${anreichern}`);
export const scanneExternesVerzeichnis = (anreichern = false): Promise<Einlesestart> => post(`/api/import/externes-verzeichnis?anreichern=${anreichern}`);
export const einlesenVorschau = (quelle: "import" | "extern"): Promise<Einlesevorschau> => get("/api/import/vorschau", { verzeichnis: quelle });

function abfrage(typen: string[], kategorie: number | null, manuell: boolean): string {
  const p = new URLSearchParams({ typen: typen.join(","), manuell_einschliessen: String(manuell) });
  if (kategorie !== null) p.set("kategorie", String(kategorie));
  return p.toString();
}

export const starteRescan = (typen: string[], kategorie: number | null = null, manuell = false): Promise<{ gestartet: boolean; grund?: string; anzahl?: number }> => post(`/api/books/rescan?${abfrage(typen, kategorie, manuell)}`);
export const rescanVorschau = (typen: string[], kategorie: number | null = null, manuell = false): Promise<Ergaenzungsvorschau> => get(`/api/books/rescan/vorschau?${abfrage(typen, kategorie, manuell)}`);
export const rescanKategorien = (typen: string[], manuell = false): Promise<Ergaenzungsregal[]> => get(`/api/books/rescan/kategorien?${abfrage(typen, null, manuell)}`);
export const holeRescanStatus = (): Promise<any> => get("/api/books/rescan/status");

/** Ein Buch mit ISBN zur Wahl aus dem Lauf "ISBN" (BF-111): der beste Kandidat und wie viele es sonst noch gibt */
export interface Isbnwahl {
  buch: Buch;
  kandidat: Isbnkandidat;
  weitere: number;
}

export const isbnWahlListe = (anzahl: number): Promise<{ gesamt: number; zeilen: Isbnwahl[] }> => get("/api/books/rescan/isbn-wahl", { anzahl });
/** Je Buch den besten Kandidaten eintragen */
export const isbnWahlAnnehmen = (buecher: number[]): Promise<{ betroffen: number }> => post("/api/books/rescan/isbn-wahl/annehmen", { buecher });
/** Alle Kandidaten dieser Bücher ablehnen; ein neuer Lauf schlägt sie nicht wieder vor */
export const isbnWahlAblehnen = (buecher: number[]): Promise<{ betroffen: number }> => post("/api/books/rescan/isbn-wahl/ablehnen", { buecher });
export const brecheRescanAb = (): Promise<any> => post("/api/books/rescan/abbrechen");
