// KI über die Leitstelle: Einordnung, Stand, Modellwahl, Anweisungen. Adresse und Schlüssel stehen in der Einrichtung des
// Servers (docs/LEITSTELLE.md), die Oberfläche wählt nur das Modell.
import { get, patch, post } from "./client";

/** GET /api/ai/status: fragt nur die Modellliste der Leitstelle, lädt nie ein Modell */
export interface KiStatus {
  /** antwortet und bietet das gewählte Modell an */
  erreichbar: boolean;
  grund?: string;
  /** Adresse der Leitstelle aus der Einrichtung */
  url?: string;
  modell?: string;
  modelle?: string[];
  /** Leitstelle eingerichtet: Adresse und Schlüssel */
  aktiviert?: boolean;
}

export interface KiEinstellungen {
  url: string;
  modell: string;
  aktiviert: boolean;
}

export interface Anweisung {
  id: number;
  schluessel: string;
  name: string;
  beschreibung: string;
  system_prompt: string;
  temperatur: number;
  max_tokens: number;
  aktiv: number | boolean;
}

export const kategorisiere = (buch: number): Promise<any> => post(`/api/ai/buch/${buch}/kategorisieren`);
export const uebernehmVorschlaege = (buch: number, kategorien: unknown[]): Promise<any> => post(`/api/ai/buch/${buch}/kategorien-uebernehmen`, { kategorien });
export const kiStatus = (): Promise<KiStatus> => get("/api/ai/status");
/** Das Modell wählen, gemerkt über einen Neustart; das Feld heißt in der Schnittstelle noch lm_studio_model */
export const waehleKiModell = (modell: string): Promise<KiEinstellungen> => patch("/api/ai/config", { lm_studio_model: modell });
export const ladeAnweisungen = (): Promise<Anweisung[]> => get("/api/ai/prompts");
export const speichereAnweisung = (id: number, daten: Partial<Anweisung>): Promise<Anweisung> => patch(`/api/ai/prompts/${id}`, daten);
