// Etiketten in Textbüchern
import { del, get, patch, post } from "./client";
import type { Etikett } from "../typen";

export const labelsFuerBuch = (buch: number): Promise<Etikett[]> => get(`/api/books/${buch}/labels`);
export const erstelleLabel = (buch: number, daten: Record<string, unknown>): Promise<Etikett> => post(`/api/books/${buch}/labels`, daten);
export const aktualisiereLabel = (id: number, daten: Record<string, unknown>): Promise<Etikett> => patch(`/api/labels/${id}`, daten);
export const loescheLabel = (id: number): Promise<unknown> => del(`/api/labels/${id}`);
