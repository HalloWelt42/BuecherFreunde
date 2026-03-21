/**
 * API-Modul: Metadatenanreicherung (Google Books, Open Library)
 */
import { get, post } from "./client.js";

/**
 * Metadaten für ein Buch suchen (Vorschau).
 * @param {number} bookId
 * @param {string} [quelle] - "google_books" oder "open_library" (ohne = beide)
 * @returns {Promise<Object>}
 */
export function sucheMetadaten(bookId, quelle) {
  const params = quelle ? `?quelle=${quelle}` : "";
  return post(`/api/metadata/buch/${bookId}/anreichern${params}`);
}

/**
 * Gefundene Metadaten auf Buch anwenden.
 * @param {number} bookId
 * @param {Object} metadata
 * @returns {Promise<import("../types/index.js").Book>}
 */
export function uebernehmMetadaten(bookId, metadata) {
  return post(`/api/metadata/buch/${bookId}/uebernehmen`, metadata);
}

/**
 * Volltext eines Buches laden.
 * @param {number} bookId
 * @returns {Promise<{volltext: string}>}
 */
export function ladeVolltext(bookId) {
  return get(`/api/metadata/buch/${bookId}/volltext`);
}

