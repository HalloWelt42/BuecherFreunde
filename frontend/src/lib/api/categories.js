/**
 * API-Modul: Kategorien
 */
import { get, post, patch, del } from "./client.js";

/**
 * Kategoriebaum laden.
 * @returns {Promise<import("../types/index.js").Category[]>}
 */
export function ladeKategorien() {
  return get("/api/categories");
}

/**
 * Einzelne Kategorie laden.
 * @param {number} id
 * @returns {Promise<import("../types/index.js").Category>}
 */
export function holeKategorie(id) {
  return get(`/api/categories/${id}`);
}

/**
 * Neue Kategorie erstellen.
 * @param {Object} daten
 * @param {string} daten.name
 * @param {number} [daten.parent_id]
 * @returns {Promise<import("../types/index.js").Category>}
 */
export function erstelleKategorie(daten) {
  return post("/api/categories", daten);
}

/**
 * Kategorie aktualisieren.
 * @param {number} id
 * @param {Object} daten
 * @returns {Promise<import("../types/index.js").Category>}
 */
export function aktualisiereKategorie(id, daten) {
  return patch(`/api/categories/${id}`, daten);
}

/**
 * Kategorie löschen.
 * @param {number} id
 * @returns {Promise<{message: string}>}
 */
export function loescheKategorie(id) {
  return del(`/api/categories/${id}`);
}

/**
 * Buch einer Kategorie zuordnen.
 * @param {number} categoryId
 * @param {number} bookId
 * @returns {Promise<{message: string}>}
 */
export function ordneBuchZu(categoryId, bookId) {
  return post(`/api/categories/${categoryId}/books/${bookId}`);
}

/**
 * Buch aus einer Kategorie entfernen.
 * @param {number} categoryId
 * @param {number} bookId
 * @returns {Promise<{message: string}>}
 */
export function entferneBuch(categoryId, bookId) {
  return del(`/api/categories/${categoryId}/books/${bookId}`);
}
