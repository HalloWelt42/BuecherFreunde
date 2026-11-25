// Bücher: Liste, Einzelnes, Umschlag, Datei, Text
import { get, patch, post } from "./client";
import type { Parameter } from "./client";
import type { Buch, BuchEinzeln, BuchListe } from "../typen";

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
export const aktualisiereBuch = (id: number, daten: Record<string, unknown>): Promise<BuchEinzeln> => patch(`/api/books/${id}`, daten);
export const bulkAction = (buecher: number[], aktion: string, wert: unknown): Promise<{ betroffen: number }> => post("/api/books/bulk", { book_ids: buecher, aktion, wert });
export const umschlagNeu = (id: number): Promise<any> => post(`/api/books/${id}/cover/neu-extrahieren`);
export const isbnScan = (id: number): Promise<any> => post(`/api/books/${id}/isbn-scan`);
export const textSeiten = (id: number, ab: number, anzahl: number): Promise<any> => get(`/api/books/${id}/textseiten`, { ab, anzahl });

export function textBildUrl(id: number, seite: number, nr: number): string {
  return `/api/books/${id}/textseiten/${seite}/bild/${nr}`;
}

/** `stand` ändert sich mit dem Bild (cover_stand), sonst mit dem Buch. */
export function coverUrl(id: number, stand?: string | number): string {
  return `/api/books/${id}/cover${stand ? `?_v=${encodeURIComponent(stand)}` : ""}`;
}

export function dateiUrl(id: number): string {
  return `/api/books/${id}/file`;
}

export function volltextSuche(id: number, wort: string, schalter: Suchschalter = {}): Promise<{ treffer: Buchtreffer[]; gesamt: number; seiten_gesamt?: number }> {
  const { limit = 500, ganzes_wort, gross_klein, regex } = schalter;
  return get(`/api/books/${id}/volltext-suche`, { q: wort, limit, ganzes_wort: ganzes_wort || undefined, gross_klein: gross_klein || undefined, regex: regex || undefined });
}
