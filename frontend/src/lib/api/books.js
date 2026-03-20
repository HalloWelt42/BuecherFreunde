/**
 * API-Modul: Bücher
 */
import { get, post, patch, del, upload, download } from "./client.js";

/**
 * Bücher mit Filtern und Pagination laden.
 * @param {Object} [params]
 * @param {number} [params.limit]
 * @param {number} [params.offset]
 * @param {string} [params.sort_by]
 * @param {string} [params.sort_dir]
 * @param {number} [params.category_id]
 * @param {number} [params.tag_id]
 * @param {boolean} [params.is_favorite]
 * @param {boolean} [params.is_to_read]
 * @param {number} [params.min_rating]
 * @param {string} [params.file_format]
 * @param {string} [params.search]
 * @returns {Promise<{books: import("../types/index.js").Book[], total: number, limit: number, offset: number}>}
 */
export function listeBooks(params) {
  return get("/api/books", params);
}

/**
 * Einzelnes Buch laden.
 * @param {number} id
 * @returns {Promise<import("../types/index.js").Book>}
 */
export function holeBuch(id) {
  return get(`/api/books/${id}`);
}

/**
 * Buch aktualisieren.
 * @param {number} id
 * @param {Object} daten
 * @returns {Promise<import("../types/index.js").Book>}
 */
export function aktualisiereBuch(id, daten) {
  return patch(`/api/books/${id}`, daten);
}

/**
 * Buch löschen.
 * @param {number} id
 * @returns {Promise<{message: string}>}
 */
export function loescheBuch(id) {
  return del(`/api/books/${id}`);
}

/**
 * Cover-URL für ein Buch.
 * @param {number} id
 * @returns {string}
 */
export function coverUrl(id) {
  return `/api/books/${id}/cover`;
}

/**
 * Buchdatei-URL (für Reader/Download).
 * @param {number} id
 * @returns {string}
 */
export function dateiUrl(id) {
  return `/api/books/${id}/file`;
}

/**
 * Cover als Blob laden.
 * @param {number} id
 * @returns {Promise<Blob>}
 */
export function ladeCover(id) {
  return download(`/api/books/${id}/cover`);
}

/**
 * Buchdatei als Blob laden.
 * @param {number} id
 * @returns {Promise<Blob>}
 */
export function ladeDatei(id) {
  return download(`/api/books/${id}/file`);
}
