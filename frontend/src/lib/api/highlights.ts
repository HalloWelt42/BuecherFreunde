// Markierungen
import { del, get, patch, post } from "./client";
import type { Markierung } from "../typen";

export const highlightsFuerBuch = (buch: number): Promise<Markierung[]> => get(`/api/books/${buch}/highlights`);
export const erstelleHighlight = (buch: number, daten: Record<string, unknown>): Promise<Markierung> => post(`/api/books/${buch}/highlights`, daten);
export const loescheHighlight = (id: number): Promise<unknown> => del(`/api/highlights/${id}`);
export const aktualisiereHighlight = (id: number, daten: Record<string, unknown>): Promise<Markierung> => patch(`/api/highlights/${id}`, daten);

/** Wo das Lesen eines Rechtecks steht (BF-123): offen, fertig (mit Text, leer: dort steht keiner) oder fehler (mit Grund) */
export interface Lesestand {
  id: number;
  stand: "offen" | "fertig" | "fehler";
  text: string;
  grund: string;
}
/** Das gerade gezogene Rechteck lesen, für das Menü daran */
export const liesBereich = (buch: number, stelle: string): Promise<Lesestand> => post(`/api/books/${buch}/lesen`, { stelle });
export const lesestand = (lesung: number): Promise<Lesestand> => get(`/api/lesen/${lesung}`);
/** Eine Markierung über ein Rechteck noch einmal lesen */
export const liesMarkierungErneut = (id: number): Promise<Lesestand> => post(`/api/highlights/${id}/lesen`, {});
