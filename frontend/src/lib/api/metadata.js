/**
 * API-Modul: Metadatenanreicherung (Open Library)
 */
import { get, post } from "./client.js";

/**
 * Metadaten für ein Buch suchen (Vorschau).
 * @param {number} bookId
 * @returns {Promise<{found: boolean, metadata: Object}>}
 */
export function sucheMetadaten(bookId) {
  return post(`/api/metadata/buch/${bookId}/anreichern`);
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
 * Einzelnes Buch anreichern (suchen + automatisch anwenden).
 * @param {number} bookId
 * @returns {Promise<{enriched: boolean, book: import("../types/index.js").Book}>}
 */
export function anreichern(bookId) {
  return post(`/api/metadata/buch/${bookId}/anreichern`);
}

/**
 * Bulk-Anreicherung für alle Bücher starten.
 * @returns {Promise<{message: string, total: number}>}
 */
export function bulkAnreichern() {
  return post("/api/metadata/bulk-anreichern");
}
