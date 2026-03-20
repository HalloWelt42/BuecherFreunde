/**
 * API-Modul: Nutzerdaten (Favoriten, Lesezeichen, Bewertung, Leseposition)
 */
import { get, post, patch } from "./client.js";

/**
 * Favorit umschalten.
 * @param {number} bookId
 * @returns {Promise<{is_favorite: boolean}>}
 */
export function toggleFavorit(bookId) {
  return post(`/api/user-data/books/${bookId}/favorite`);
}

/**
 * Zum-Lesen umschalten.
 * @param {number} bookId
 * @returns {Promise<{is_to_read: boolean}>}
 */
export function toggleZumLesen(bookId) {
  return post(`/api/user-data/books/${bookId}/to-read`);
}

/**
 * Bewertung setzen (0-5).
 * @param {number} bookId
 * @param {number} rating
 * @returns {Promise<{rating: number}>}
 */
export function setzeBewertung(bookId, rating) {
  return patch(`/api/user-data/books/${bookId}/rating`, { rating });
}

/**
 * Leseposition speichern.
 * @param {number} bookId
 * @param {string} position - Seitenzahl, CFI oder Prozentwert
 * @returns {Promise<{reading_position: string}>}
 */
export function speichereLeseposition(bookId, position) {
  return patch(`/api/user-data/books/${bookId}/position`, {
    reading_position: position,
  });
}

/**
 * Zuletzt gelesene Bücher.
 * @param {number} [limit]
 * @returns {Promise<import("../types/index.js").Book[]>}
 */
export function zuletztGelesen(limit) {
  return get("/api/user-data/recently-read", { limit });
}
