/**
 * API-Modul: Konfiguration und Dienste
 */
import { get, patch } from "./client.js";

/**
 * Öffentliche Konfiguration laden (ohne Auth).
 * @returns {Promise<Object>}
 */
export function ladeConfig() {
  return get("/api/config");
}

/**
 * Versionsnummer laden (ohne Auth).
 * @returns {Promise<{version: string}>}
 */
export function ladeVersion() {
  return get("/api/config/version");
}

/**
 * Konfiguration aktualisieren.
 * @param {Object} daten
 * @returns {Promise<Object>}
 */
export function aktualisiereConfig(daten) {
  return patch("/api/config", daten);
}

/**
 * KI-Status prüfen (LM Studio erreichbar?).
 * @returns {Promise<{available: boolean, model: string, url: string}>}
 */
export function kiStatus() {
  return get("/api/ai/status");
}

/**
 * Health-Check.
 * @returns {Promise<{status: string, version: string}>}
 */
export function healthCheck() {
  return get("/api/health");
}
