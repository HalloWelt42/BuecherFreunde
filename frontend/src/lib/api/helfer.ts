// Helfer beim Lesen: Nachschlagen und das Gespräch mit dem Assistenten
import { anfrage, get, post } from "./client";

export interface Nachschlagtreffer {
  buch: string;
  buchtitel: string;
  pfad: string;
  titel: string;
  auszug: string;
  anker: string;
  bild: string;
}

export interface Nachschlagartikel {
  buch: string;
  buchtitel: string;
  pfad: string;
  titel: string;
  html: string;
  anker: string;
  bild: string;
  abschnitte: { anker: string; titel: string }[];
  adresse: string;
}

export const sucheNach = (q: string, nurTitel = false): Promise<Nachschlagtreffer[]> => get("/api/nachschlag/suche", { q, nur_titel: nurTitel || undefined });
export const ladeArtikel = (buch: string, pfad: string, q = "", anker = ""): Promise<Nachschlagartikel> => get("/api/nachschlag/artikel", { buch, pfad, q, anker });

export interface Stelle {
  buch?: number;
  seite?: number;
  text?: string;
}

export interface Gestellt {
  chat: string;
  zug: string;
  adresse: string;
}

export interface Antwortbeleg {
  nummer: string;
  titel: string;
  seite: string;
  verweis: string;
}

export type Antwortzeile =
  | { art: "stand"; antwort: string; zustand: string; wartet_auf: string; fehler: string; belege: Antwortbeleg[] }
  | { art: "text"; text: string; ab: number; neu: boolean };

/** `nachsehen`: auch in Büchern, Dateien und im Netz; ohne antwortet er schnell aus der Stelle allein. */
export const stelleFrage = (frage: string, stelle: Stelle, chat = "", nachsehen = true): Promise<Gestellt> => post("/api/gespraech", { frage, stelle, chat, nachsehen });
export const antwortStrom = (chat: string, zug: string, abbruch: AbortSignal): Promise<Response> => anfrage(`/api/gespraech/${chat}/${zug}`, { signal: abbruch });
export const brichAntwortAb = (zug: string): Promise<Response> => anfrage(`/api/gespraech/zuege/${zug}/abbrechen`, { method: "POST" });
