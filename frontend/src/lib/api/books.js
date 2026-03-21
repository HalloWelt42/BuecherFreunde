/**
 * API-Modul: Bücher
 */
import { get, post, patch, del, upload, download, getToken } from "./client.js";

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
 * Aehnliche Buecher laden (gleicher Autor, gleiche Kategorie).
 * @param {number} id
 * @returns {Promise<{vom_autor: Array, in_kategorie: Array}>}
 */
export function aehnlicheBuecher(id) {
  return get(`/api/books/${id}/aehnliche`);
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
 * Massenbearbeitung für mehrere Bücher.
 * @param {number[]} bookIds
 * @param {string} aktion - "löschen", "kategorie_zuweisen", "tag_zuweisen", "favorit", "zu_lesen"
 * @param {*} [wert]
 * @returns {Promise<{betroffen: number, aktion: string}>}
 */
export function bulkAction(bookIds, aktion, wert) {
  return post("/api/books/bulk", { book_ids: bookIds, aktion, wert });
}

/**
 * Cover-URL für ein Buch.
 * @param {number} id
 * @returns {string}
 */
export function coverUrl(id, updatedAt) {
  const token = getToken();
  let url = `/api/books/${id}/cover?token=${encodeURIComponent(token)}`;
  if (updatedAt) {
    url += `&_v=${encodeURIComponent(updatedAt)}`;
  }
  return url;
}

/**
 * Buchdatei-URL (für Reader/Download).
 * @param {number} id
 * @returns {string}
 */
export function dateiUrl(id) {
  const token = getToken();
  return `/api/books/${id}/file?token=${encodeURIComponent(token)}`;
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

/**
 * Volltext eines Buches durchsuchen.
 * @param {number} id
 * @param {string} suchbegriff
 * @param {number} [limit]
 * @returns {Promise<{treffer: Array, gesamt: number, seiten_gesamt: number, suchbegriff: string}>}
 */
export function volltextSuche(id, suchbegriff, limit = 50) {
  return get(`/api/books/${id}/volltext-suche`, { q: suchbegriff, limit });
}
