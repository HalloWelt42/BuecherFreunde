// Gemeinfreie Bücher: Suche und Übernahme; den Stand der Übernahme führt die Annahme (/api/annahme, Quelle gemeinfrei)
import { get, post } from "./client";

export interface Fundbuch {
  gutenberg_id: number;
  titel: string;
  autor: string;
  sprachen: string[];
  download_url: string;
  download_format: string;
  cover_url: string;
  download_count: number;
}

export interface Fundliste {
  gesamt: number;
  seite: number;
  naechste: string | null;
  vorherige: string | null;
  buecher: Fundbuch[];
}

export const sucheGemeinfreie = (q: string, sprache: string, seite: number): Promise<Fundliste> => get("/api/gutenberg/suche", { q: q.trim(), sprache: sprache.trim(), seite });
export const uebernimmGemeinfreie = (buecher: Partial<Fundbuch>[]): Promise<{ gestartet: boolean; anzahl: number }> => post("/api/gutenberg/import", { buecher });
