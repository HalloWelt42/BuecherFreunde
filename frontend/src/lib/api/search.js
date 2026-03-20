/**
 * API-Modul: Volltextsuche
 */
import { get, post } from "./client.js";

/**
 * Volltextsuche durchführen.
 * @param {string} query
 * @param {Object} [params]
 * @param {number} [params.limit]
 * @param {number} [params.offset]
 * @returns {Promise<{results: import("../types/index.js").SearchResult[], total: number, query: string}>}
 */
export function suche(query, params) {
  return get("/api/search", { q: query, ...params });
}

/**
 * Suchvorschläge (Autovervollständigung).
 * @param {string} query
 * @returns {Promise<{suggestions: string[]}>}
 */
export function vorschlaege(query) {
  return get("/api/search/suggest", { q: query });
}

/**
 * FTS-Index komplett neu aufbauen.
 * @returns {Promise<{message: string}>}
 */
export function indexNeuAufbauen() {
  return post("/api/search/reindex");
}
