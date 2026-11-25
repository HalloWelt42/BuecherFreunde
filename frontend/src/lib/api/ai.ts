// KI: Einordnung, Verbindung, Anweisungen
import { get, patch, post } from "./client";

export interface KiStatus {
  erreichbar: boolean;
  grund?: string;
  url?: string;
  modell?: string;
  modelle?: string[];
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

export interface KiTreffer {
  url: string;
  modelle: number;
}

export const kategorisiere = (buch: number): Promise<any> => post(`/api/ai/buch/${buch}/kategorisieren`);
export const uebernehmVorschlaege = (buch: number, kategorien: unknown[]): Promise<any> => post(`/api/ai/buch/${buch}/kategorien-uebernehmen`, { kategorien });
export const kiStatus = (): Promise<KiStatus> => get("/api/ai/status");
export const kiEinstellungen = (): Promise<KiEinstellungen> => get("/api/ai/config");
export const speichereKi = (daten: { lm_studio_url?: string; lm_studio_model?: string }): Promise<KiEinstellungen> => patch("/api/ai/config", daten);
export const sucheKiImNetz = (): Promise<{ gefunden: KiTreffer[] }> => get("/api/ai/scan");
export const ladeAnweisungen = (): Promise<Anweisung[]> => get("/api/ai/prompts");
export const speichereAnweisung = (id: number, daten: Partial<Anweisung>): Promise<Anweisung> => patch(`/api/ai/prompts/${id}`, daten);
