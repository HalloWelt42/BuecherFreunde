// Suche nach Wörtern
import { get, post } from "./client";
import type { Materialtreffer, Markierungstreffer, Treffer } from "../typen";

export interface Suchantwort {
  treffer: Treffer[];
  gesamt: number;
  aktive_filter: Record<string, string>;
  /** Treffer im Begleitmaterial, nur auf der ersten Seite (BF-81) */
  material?: Materialtreffer[];
  /** Treffer in den eigenen Markierungen, nur auf der ersten Seite (BF-123) */
  markierungen?: Markierungstreffer[];
}

export interface Suchvorschlag {
  id: number;
  titel: string;
  autor: string;
}

export const suche = (wort: string, params: { limit?: number; offset?: number } = {}): Promise<Suchantwort> => get("/api/search", { q: wort, ...params });
export const vorschlaege = (wort: string): Promise<{ vorschlaege: Suchvorschlag[] }> => get("/api/search/vorschlaege", { q: wort });
export const indexNeuAufbauen = (): Promise<{ indexiert: number }> => post("/api/search/index-neu-aufbauen");
