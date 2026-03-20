/**
 * API-Modul: Tags
 */
import { get, post, patch, del } from "./client.js";

/**
 * Alle Tags laden.
 * @returns {Promise<import("../types/index.js").Tag[]>}
 */
export function ladeTags() {
  return get("/api/tags");
}

/**
 * Neuen Tag erstellen.
 * @param {Object} daten
 * @param {string} daten.name
 * @param {string} [daten.color]
 * @returns {Promise<import("../types/index.js").Tag>}
 */
export function erstelleTag(daten) {
  return post("/api/tags", daten);
}

/**
 * Tag aktualisieren.
 * @param {number} id
 * @param {Object} daten
 * @returns {Promise<import("../types/index.js").Tag>}
 */
export function aktualisiereTag(id, daten) {
  return patch(`/api/tags/${id}`, daten);
}

/**
 * Tag löschen.
 * @param {number} id
 * @returns {Promise<{message: string}>}
 */
export function loescheTag(id) {
  return del(`/api/tags/${id}`);
}

/**
 * Tag einem Buch zuordnen.
 * @param {number} tagId
 * @param {number} bookId
 * @returns {Promise<{message: string}>}
 */
export function ordneBuchZu(tagId, bookId) {
  return post(`/api/tags/${tagId}/books/${bookId}`);
}

/**
 * Tag von einem Buch entfernen.
 * @param {number} tagId
 * @param {number} bookId
 * @returns {Promise<{message: string}>}
 */
export function entferneBuch(tagId, bookId) {
  return del(`/api/tags/${tagId}/books/${bookId}`);
}
