// KI: Einordnung, Verbindung, Anweisungen
import { get, patch, post } from "./client";

export interface KiStatus {
  erreichbar: boolean;
  grund?: string;
  url?: string;
  modell?: string;
  aktiviert?: boolean;
}

export const kategorisiere = (buch: number): Promise<any> => post(`/api/ai/buch/${buch}/kategorisieren`);
export const uebernehmVorschlaege = (buch: number, kategorien: unknown[]): Promise<any> => post(`/api/ai/buch/${buch}/kategorien-uebernehmen`, { kategorien });
export const kiStatus = (): Promise<KiStatus> => get("/api/ai/status");
export const kiEinstellungen = (): Promise<{ url: string; modell: string; aktiviert: boolean }> => get("/api/ai/config");
export const speichereKi = (daten: Record<string, unknown>): Promise<any> => patch("/api/ai/config", daten);
export const sucheKiImNetz = (): Promise<any> => get("/api/ai/scan");
export const ladeAnweisungen = (): Promise<any> => get("/api/ai/prompts");
export const speichereAnweisung = (id: number, daten: Record<string, unknown>): Promise<any> => patch(`/api/ai/prompts/${id}`, daten);
