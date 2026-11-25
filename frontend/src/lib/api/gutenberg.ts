// Gemeinfreie Bücher: Suche und Übernahme
import { del, get, getToken, post } from "./client";

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

export interface Uebernahmeergebnis {
  gutenberg_id: number;
  titel: string;
  status: "ok" | "duplikat" | "fehler";
  detail: string;
  book_id?: number;
}

export interface Uebernahmestand {
  laeuft: boolean;
  gesamt: number;
  fertig: number;
  fehler: number;
  duplikate: number;
  aktuell: string;
  ergebnisse: Uebernahmeergebnis[];
}

export const sucheGemeinfreie = (q: string, sprache: string, seite: number): Promise<Fundliste> => get("/api/gutenberg/suche", { q: q.trim(), sprache: sprache.trim(), seite });
export const uebernimmGemeinfreie = (buecher: Partial<Fundbuch>[]): Promise<{ gestartet: boolean; anzahl: number }> => post("/api/gutenberg/import", { buecher });
export const standGemeinfreie = (): Promise<Uebernahmestand> => get("/api/gutenberg/import/status");
export const setzeGemeinfreieZurueck = (): Promise<unknown> => del("/api/gutenberg/import/reset");

/** Ereignisstrom der Übernahme; endet, wenn der Server fertig ist */
export function ereignisseGemeinfreie(tun: (stand: Uebernahmestand) => void, beiFehler: () => void): () => void {
  const strom = new EventSource(`/api/gutenberg/import/events?token=${encodeURIComponent(getToken())}`);
  strom.onmessage = (e) => {
    try {
      tun(JSON.parse(e.data) as Uebernahmestand);
    } catch {
      // unvollständige Zeile: die nächste bringt den ganzen Stand
    }
  };
  strom.onerror = () => {
    strom.close();
    beiFehler();
  };
  return () => strom.close();
}
