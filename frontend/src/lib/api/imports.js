/**
 * API-Modul: Import
 */
import { get, post, del, upload, sse } from "./client.js";

/**
 * Einzelne Datei hochladen.
 * @param {File} file
 * @returns {Promise<import("../types/index.js").ImportTask>}
 */
export function ladeDateiHoch(file) {
  const formData = new FormData();
  formData.append("file", file);
  return upload("/api/import/upload", formData);
}

/**
 * Mehrere Dateien hochladen.
 * @param {File[]} files
 * @returns {Promise<import("../types/index.js").ImportTask[]>}
 */
export function ladeDateienHoch(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return upload("/api/import/upload-mehrere", formData);
}

/**
 * Import-Verzeichnis scannen.
 * @returns {Promise<{tasks: import("../types/index.js").ImportTask[], count: number}>}
 */
export function scanneImportVerzeichnis() {
  return post("/api/import/scan");
}

/**
 * Externes Verzeichnis scannen.
 * @returns {Promise<{tasks: import("../types/index.js").ImportTask[], count: number}>}
 */
export function scanneExternesVerzeichnis() {
  return post("/api/import/externes-verzeichnis");
}

/**
 * Import-Status aller Aufgaben.
 * @returns {Promise<import("../types/index.js").ImportTask[]>}
 */
export function holeImportStatus() {
  return get("/api/import/status");
}

/**
 * Import-Vorschau (gefundene Dateien).
 * @param {string} source - "import" oder "external"
 * @returns {Promise<{files: string[], count: number}>}
 */
export function importVorschau(source) {
  return get("/api/import/vorschau", { verzeichnis: source === "external" ? "extern" : "import" });
}

/**
 * SSE-Stream für Import-Fortschritt.
 * @param {(event: {type: string, data: *}) => void} onEvent
 * @param {(error: Error) => void} [onError]
 * @returns {{ close: () => void }}
 */
export function importEvents(onEvent, onError) {
  return sse("/api/import/events", onEvent, onError);
}

/**
 * Abgeschlossene Import-Tasks aus der DB löschen.
 * @returns {Promise<{aufgaben: Array}>}
 */
export function bereinigeImportTasks() {
  return del("/api/import/bereinigen");
}
