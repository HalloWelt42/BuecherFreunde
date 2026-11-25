// Markierungen
import { del, get, patch, post } from "./client";
import type { Markierung } from "../typen";

export const highlightsFuerBuch = (buch: number): Promise<Markierung[]> => get(`/api/books/${buch}/highlights`);
export const erstelleHighlight = (buch: number, daten: Record<string, unknown>): Promise<Markierung> => post(`/api/books/${buch}/highlights`, daten);
export const loescheHighlight = (id: number): Promise<unknown> => del(`/api/highlights/${id}`);
export const aktualisiereHighlight = (id: number, daten: Record<string, unknown>): Promise<Markierung> => patch(`/api/highlights/${id}`, daten);
