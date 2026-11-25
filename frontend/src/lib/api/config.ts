// Grundeinstellungen, Fassung, Zustand
import { get, getToken, post } from "./client";

export interface Erreichbarkeit {
  erreichbar: boolean;
  grund?: string;
  info?: string;
  url?: string;
}

export interface Verzeichnisse {
  datenbank: string;
  speicher: string;
  import: string;
  extern: string;
}

export interface Sicherung {
  filename: string;
  size: number;
  created_at: string;
}

export interface Defekt {
  id: number;
  titel: string;
  autor: string;
  format: string;
  dateiname: string;
  groesse: number;
  grund: string;
}

export interface Dateipruefung {
  geprueft: number;
  defekt: number;
  eintraege: Defekt[];
}

export interface AppAngaben {
  name: string;
  kellerwolke: string;
  besitzer: string | null;
  eingerichtet: boolean;
}

export const ladeConfig = (): Promise<any> => get("/api/config");
export const ladeVersion = (): Promise<{ version: string }> => get("/api/config/version");
export const ladePfade = (): Promise<Verzeichnisse> => get("/api/config/paths");
export const healthCheck = (): Promise<{ status: string }> => get("/api/health");
export const gutenbergStatus = (): Promise<Erreichbarkeit> => get("/api/gutenberg/status");
export const quellenStatus = (): Promise<Record<"google_books" | "open_library" | "wikipedia", Erreichbarkeit>> => get("/api/metadata/verbindungsstatus");
export const sicherungAnlegen = (): Promise<{ message: string; filename: string; size: number; neu: boolean }> => post("/api/backup/create");
export const sicherungen = (): Promise<Sicherung[]> => get("/api/backup/list");
/** Nur Bericht: öffnet jede Datei einmal, ändert nichts */
export const pruefeDateien = (): Promise<Dateipruefung> => post("/api/wartung/defekte-pruefen");

export function sicherungAdresse(datei: string): string {
  return `/api/backup/download?${new URLSearchParams({ filename: datei, token: getToken() })}`;
}
