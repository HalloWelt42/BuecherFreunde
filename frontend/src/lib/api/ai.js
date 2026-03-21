/**
 * API-Modul: KI-Kategorisierung (LM Studio)
 */
import { get, post } from "./client.js";

/**
 * KI-Kategorisierung für ein Buch durchführen.
 * @param {number} bookId
 * @returns {Promise<{suggestions: Array<{category: string, confidence: number}>}>}
 */
export function kategorisiere(bookId) {
  return post(`/api/ai/buch/${bookId}/kategorisieren`);
}

/**
 * KI-Vorschläge akzeptieren und auf Buch anwenden.
 * @param {number} bookId
 * @param {string[]} categories - Akzeptierte Kategorienamen
 * @returns {Promise<{message: string}>}
 */
export function uebernehmVorschlaege(bookId, kategorien) {
  return post(`/api/ai/buch/${bookId}/kategorien-uebernehmen`, { kategorien });
}

/**
 * KI-Dienst-Status prüfen.
 * @returns {Promise<{available: boolean, model: string, url: string}>}
 */
export function status() {
  return get("/api/ai/status");
}
