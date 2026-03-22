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
export function scanneImportVerzeichnis(anreichern = false) {
  return post(`/api/import/scan?anreichern=${anreichern}`);
}

/**
 * Externes Verzeichnis scannen.
 * @param {boolean} anreichern - Metadaten via Open Library anreichern
 * @returns {Promise<{tasks: import("../types/index.js").ImportTask[], count: number}>}
 */
export function scanneExternesVerzeichnis(anreichern = false) {
  return post(`/api/import/externes-verzeichnis?anreichern=${anreichern}`);
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

/**
 * Alle wartenden Import-Tasks abbrechen.
 * @returns {Promise<Object>}
 */
export function brecheImportAb() {
  return post("/api/import/abbrechen");
}

/**
 * Selektiven Rescan starten.
 * @param {string[]} typen - z.B. ["cover", "isbn", "metadaten", "volltext"]
 * @param {number|null} kategorie - Kategorie-ID oder null fuer alle
 * @param {boolean} manuellEinschliessen
 * @returns {Promise<{gestartet: boolean, anzahl?: number}>}
 */
export function starteRescan(typen, kategorie = null, manuellEinschliessen = false) {
  let url = `/api/books/rescan?typen=${typen.join(",")}&manuell_einschliessen=${manuellEinschliessen}`;
  if (kategorie !== null) url += `&kategorie=${kategorie}`;
  return post(url);
}

/**
 * Rescan-Status abfragen.
 * @returns {Promise<Object>}
 */
export function holeRescanStatus() {
  return get("/api/books/rescan/status");
}

/**
 * Laufenden Rescan abbrechen.
 * @returns {Promise<Object>}
 */
export function brecheRescanAb() {
  return post("/api/books/rescan/abbrechen");
}

/**
 * Rescan-Vorschau: wie viele Buecher betroffen.
 * @param {string[]} typen
 * @param {number|null} kategorie
 * @param {boolean} manuellEinschliessen
 * @returns {Promise<Object>}
 */
export function rescanVorschau(typen, kategorie = null, manuellEinschliessen = false) {
  let url = `/api/books/rescan/vorschau?typen=${typen.join(",")}&manuell_einschliessen=${manuellEinschliessen}`;
  if (kategorie !== null) url += `&kategorie=${kategorie}`;
  return get(url);
}

/**
 * Rescan-Kategorien: betroffene Buecher pro Kategorie.
 * @param {string[]} typen
 * @param {boolean} manuellEinschliessen
 * @returns {Promise<Array>}
 */
export function rescanKategorien(typen, manuellEinschliessen = false) {
  return get(`/api/books/rescan/kategorien?typen=${typen.join(",")}&manuell_einschliessen=${manuellEinschliessen}`);
}
