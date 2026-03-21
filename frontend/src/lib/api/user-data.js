/**
 * API-Modul: Nutzerdaten (Favoriten, Lesezeichen, Bewertung, Leseposition)
 */
import { get, patch } from "./client.js";

/**
 * Favorit umschalten.
 * @param {number} bookId
 * @returns {Promise<{book_id: number, ist_favorit: boolean}>}
 */
export function toggleFavorit(bookId) {
  return patch(`/api/books/${bookId}/favorit`);
}

/**
 * Zum-Lesen umschalten.
 * @param {number} bookId
 * @returns {Promise<{book_id: number, zu_lesen: boolean}>}
 */
export function toggleZumLesen(bookId) {
  return patch(`/api/books/${bookId}/zu-lesen`);
}

/**
 * Bewertung setzen (0-5).
 * @param {number} bookId
 * @param {number} bewertung
 * @returns {Promise<{book_id: number, bewertung: number}>}
 */
export function setzeBewertung(bookId, bewertung) {
  return patch(`/api/books/${bookId}/bewertung`, { bewertung });
}

/**
 * Leseposition speichern.
 * @param {number} bookId
 * @param {string} position - Seitenzahl, CFI oder Prozentwert
 * @returns {Promise<{book_id: number, position: string}>}
 */
export function speichereLeseposition(bookId, position) {
  return patch(`/api/books/${bookId}/leseposition`, { position });
}

/**
 * Zuletzt gelesene Bücher.
 * @param {number} [limit]
 * @returns {Promise<import("../types/index.js").Book[]>}
 */
export function zuletztGelesen(limit) {
  return get("/api/books/recently-read", { limit });
}
