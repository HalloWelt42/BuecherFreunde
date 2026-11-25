// Was Lesende an einem Buch merken
import { get, patch } from "./client";
import type { Buch } from "../typen";

export const toggleFavorit = (buch: number): Promise<{ ist_favorit: boolean }> => patch(`/api/books/${buch}/favorit`);
export const toggleZumLesen = (buch: number): Promise<{ zu_lesen: boolean }> => patch(`/api/books/${buch}/zu-lesen`);
export const toggleGelesen = (buch: number): Promise<{ gelesen: boolean }> => patch(`/api/books/${buch}/gelesen`);
export const setzeBewertung = (buch: number, bewertung: number): Promise<{ bewertung: number }> => patch(`/api/books/${buch}/bewertung`, { bewertung });
export const speichereLeseposition = (buch: number, position: string): Promise<unknown> => patch(`/api/books/${buch}/leseposition`, { position });
export const zuletztGelesen = (limit: number): Promise<Buch[]> => get("/api/books/recently-read", { limit });
