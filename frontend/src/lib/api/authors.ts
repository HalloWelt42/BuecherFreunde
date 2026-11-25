// Autoren
import { del, get, patch, post } from "./client";
import type { Parameter } from "./client";

export interface Autor {
  id: number;
  name: string;
  photo_path: string;
  birth_year: number | null;
  death_year: number | null;
  nationality: string;
  book_count: number;
}

export interface Autorenliste {
  autoren: Autor[];
  gesamt: number;
  seite: number;
  seiten_gesamt: number;
}

export interface Autorbuch {
  id: number;
  title: string;
  year: number | null;
  file_format: string;
  cover_path: string;
  isbn: string;
  role: string;
}

export interface Werk {
  id: number;
  wikidata_id: string | null;
  titel: string;
  book_id: number | null;
}

export interface Autoreneinzeln extends Omit<Autor, "book_count"> {
  biography: string;
  beschreibung: string;
  wikidata_id: string;
  wikipedia_url: string;
  website: string;
  quelle: string;
  konfidenz: string;
  score: number;
  books: Autorbuch[];
  werke: Werk[];
}

export interface Autorvorschlag {
  name?: string;
  biography?: string;
  beschreibung?: string;
  birth_year?: number | null;
  death_year?: number | null;
  nationality?: string;
  wikidata_id?: string;
  wikipedia_url?: string;
  photo_url?: string;
  konfidenz?: string;
  score?: number;
  quelle?: string;
  werke?: { titel: string; wikidata_id?: string }[];
}

export interface Anreicherung {
  angereichert: boolean;
  grund?: string;
  vorschlag?: Autorvorschlag;
  aktuell?: Record<string, unknown> & { hat_foto?: boolean };
  buecher_im_system?: { id: number; title: string; isbn: string }[];
}

export interface Uebernahme {
  uebernommen?: boolean;
  zusammengefuehrt?: boolean;
  ziel_autor_id?: number;
  ziel_autor_name?: string;
}

export interface Autorenstatistik {
  gesamt: number;
  mit_biografie: number;
  mit_foto: number;
  mit_wikidata: number;
}

export interface Neubildung {
  neu_angelegt: number;
  verknuepft: number;
  beibehalten: number;
  gesamt: number;
  buecher_verarbeitet: number;
}

/** Ein Ereignis des Abgleichs, je nach typ mit anderen Angaben */
export interface Abgleichereignis {
  typ: "start" | "suche" | "gefunden" | "nicht_gefunden" | "fehler" | "fertig" | "abgebrochen";
  gesamt?: number;
  index?: number;
  autor_id?: number;
  name?: string;
  vorschlag?: Autorvorschlag;
  uebernommen?: boolean;
  fehler?: string | number;
}

export const holeAutoren = (params: Parameter = {}): Promise<Autorenliste> => get("/api/authors", params);
export const holeAutor = (id: number): Promise<Autoreneinzeln> => get(`/api/authors/${id}`);
export const aktualisiereAutor = (id: number, daten: Record<string, unknown>): Promise<Autoreneinzeln> => patch(`/api/authors/${id}`, daten);
export const reichereAutorAn = (id: number): Promise<Anreicherung> => post(`/api/authors/${id}/anreichern`);
export const uebernehmAutorenDaten = (id: number, felder: Record<string, unknown>): Promise<Uebernahme> => post(`/api/authors/${id}/anreichern/uebernehmen`, felder);
export const autorenStatistik = (): Promise<Autorenstatistik> => get("/api/authors/statistik/uebersicht");
export const brecheBatchScanAb = (): Promise<unknown> => post("/api/authors/scanner/abbrechen");
export const loescheVerwaiste = (): Promise<{ gelöscht: number; autoren: string[] }> => del("/api/authors/verwaist");
export const resyncAutoren = (): Promise<Neubildung> => post("/api/authors/resync");

export interface Abgleichoptionen {
  nurOhneWikidata?: boolean;
  autoUebernehmen?: boolean;
}

/** Ereignisstrom des Abgleichs; schließt sich nach einem Fehler */
export function batchScanEvents(optionen: Abgleichoptionen, tun: (ereignis: Abgleichereignis) => void, beiFehler?: () => void): { close: () => void } {
  const p = new URLSearchParams();
  p.set("nur_ohne_wikidata", String(optionen.nurOhneWikidata !== false));
  if (optionen.autoUebernehmen) p.set("auto_uebernehmen", "true");
  const strom = new EventSource(`/api/authors/scanner/events?${p}`);
  strom.onmessage = (e) => {
    try {
      tun(JSON.parse(e.data) as Abgleichereignis);
    } catch {
      // unvollständige Zeile
    }
  };
  strom.onerror = () => {
    strom.close();
    beiFehler?.();
  };
  return { close: () => strom.close() };
}

export function autorenFotoUrl(id: number, groesse: "normal" | "thumb" | "mini" = "normal"): string {
  return `/api/authors/${id}/foto${groesse !== "normal" ? `?groesse=${groesse}` : ""}`;
}
