// Buchnotizen
import { del, get, patch, post } from "./client";
import type { Notiz } from "../typen";

export const notizenFuerBuch = (buch: number): Promise<Notiz[]> => get(`/api/books/${buch}/notes`);
export const erstelleNotiz = (buch: number, daten: Record<string, unknown>): Promise<Notiz> => post(`/api/books/${buch}/notes`, daten);
export const aktualisiereNotiz = (id: number, daten: Record<string, unknown>): Promise<Notiz> => patch(`/api/notes/${id}`, daten);
export const loescheNotiz = (id: number): Promise<unknown> => del(`/api/notes/${id}`);
