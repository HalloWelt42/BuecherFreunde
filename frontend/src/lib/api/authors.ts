// Autoren
import { del, get, getToken, patch, post } from "./client";
import type { Parameter } from "./client";

export const holeAutoren = (params: Parameter = {}): Promise<any> => get("/api/authors", params);
export const holeAutor = (id: number): Promise<any> => get(`/api/authors/${id}`);
export const aktualisiereAutor = (id: number, daten: Record<string, unknown>): Promise<any> => patch(`/api/authors/${id}`, daten);
export const reichereAutorAn = (id: number): Promise<any> => post(`/api/authors/${id}/anreichern`);
export const uebernehmAutorenDaten = (id: number, felder: Record<string, unknown>): Promise<any> => post(`/api/authors/${id}/anreichern/uebernehmen`, felder);
export const autorenStatistik = (): Promise<any> => get("/api/authors/statistik/uebersicht");
export const brecheBatchScanAb = (): Promise<any> => post("/api/authors/scanner/abbrechen");
export const loescheVerwaiste = (): Promise<any> => del("/api/authors/verwaist");
export const resyncAutoren = (): Promise<any> => post("/api/authors/resync");

export interface Abgleichoptionen {
  nurOhneWikidata?: boolean;
  autoUebernehmen?: boolean;
}

/** Ereignisstrom des Abgleichs; schließt sich nach einem Fehler */
export function batchScanEvents(optionen: Abgleichoptionen, tun: (daten: any) => void, beiFehler?: () => void): { close: () => void } {
  const p = new URLSearchParams({ token: getToken() });
  if (optionen.nurOhneWikidata !== false) p.set("nur_ohne_wikidata", "true");
  if (optionen.autoUebernehmen) p.set("auto_uebernehmen", "true");
  const strom = new EventSource(`/api/authors/scanner/events?${p}`);
  strom.onmessage = (e) => {
    try {
      tun(JSON.parse(e.data));
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
  const p = new URLSearchParams({ token: getToken() });
  if (groesse !== "normal") p.set("groesse", groesse);
  return `/api/authors/${id}/foto?${p}`;
}
