// Gemeinfreie Bücher: der eigene Katalog (BF-98), Vorschläge beim Tippen, die ausdrückliche Suche bei Gutendex mit Rückfall auf
// den Katalog, Übernahme und das Holen in eine Lücke; den Stand der Übernahme führt die Annahme (/api/annahme, Quelle gemeinfrei)
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

/** Woher eine Liste kommt: vom Suchdienst Gutendex oder aus dem eigenen Katalog (Vorschläge, Rückfall) */
export type Fundherkunft = "gutendex" | "katalog";

export interface Fundliste {
  gesamt: number;
  seite: number;
  naechste: string | null;
  vorherige: string | null;
  buecher: Fundbuch[];
  herkunft?: Fundherkunft;
  /** warum die Treffer aus dem eigenen Katalog kommen, als Satz */
  hinweis?: string;
}

export interface Katalogstand {
  da: boolean;
  anzahl: number;
  /** Datum der Datei auf dem Spiegel, JJJJ-MM-TT */
  stand: string | null;
  geholt_am: string | null;
  alter_tage: number | null;
  faellig: boolean;
  erneuern_tage: number;
  laeuft: boolean;
  schritt: "" | "holen" | "bauen";
  /** Byte: geholt, beim Bauen gelesen */
  erledigt: number;
  gesamt: number | null;
  /** warum der letzte Lauf scheiterte */
  grund: string;
  /** so lange wartet "Bei Gutendex suchen" */
  suche_geduld_s: number;
}

export type Gemeinfreiangaben = Pick<Fundbuch, "gutenberg_id" | "titel" | "autor" | "download_url" | "download_format" | "cover_url">;

export const angabenAus = ({ gutenberg_id, titel, autor, download_url, download_format, cover_url }: Fundbuch): Gemeinfreiangaben => ({ gutenberg_id, titel, autor, download_url, download_format, cover_url });

/** Ausdrücklich bei Gutendex; das Signal bricht das Warten ab */
export const sucheGemeinfreie = (q: string, sprache: string, seite: number, signal?: AbortSignal): Promise<Fundliste> => get("/api/gutenberg/suche", { q: q.trim(), sprache: sprache.trim(), seite }, { signal });
/** Beim Tippen: nur der eigene Katalog, kein Dienst im Netz */
export const schlageGemeinfreieVor = (q: string, sprache: string, seite: number): Promise<Fundliste> => get("/api/gutenberg/vorschlaege", { q: q.trim(), sprache: sprache.trim(), seite });
export const uebernimmGemeinfreie = (buecher: Gemeinfreiangaben[]): Promise<{ gestartet: boolean; anzahl: number }> => post("/api/gutenberg/import", { buecher });
export const ladeKatalogstand = (): Promise<Katalogstand> => get("/api/gutenberg/katalog");
/** Holen oder erneuern; läuft es schon, bleibt es bei diesem Lauf */
export const holeKatalog = (): Promise<Katalogstand> => post("/api/gutenberg/katalog");
/** In die Lücke holen: geholt wie jedes gemeinfreie Buch, mit Halt in einer Vorschau mit Sammlung, Band und Sprache der Lücke */
export const holeInDieLuecke = (buch: Gemeinfreiangaben, sammlung_id: number, band: string, sprache: string): Promise<{ vorschau: string }> => post("/api/gutenberg/luecke", { buch, sammlung_id, band, sprache });
