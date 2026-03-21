/**
 * API-Modul: Autoren
 */
import { get, post, patch, del, getToken } from "./client.js";

/**
 * Autoren-Liste laden (paginiert).
 * @param {Object} [params]
 * @returns {Promise<Object>}
 */
export function holeAutoren(params = {}) {
  const query = new URLSearchParams();
  if (params.seite) query.set("seite", params.seite);
  if (params.pro_seite) query.set("pro_seite", params.pro_seite);
  if (params.suche) query.set("suche", params.suche);
  if (params.sortierung) query.set("sortierung", params.sortierung);
  if (params.richtung) query.set("richtung", params.richtung);
  if (params.hat_foto !== undefined) query.set("hat_foto", params.hat_foto);
  if (params.hat_bio !== undefined) query.set("hat_bio", params.hat_bio);
  const qs = query.toString();
  return get(`/api/authors${qs ? "?" + qs : ""}`);
}

/**
 * Einzelnen Autor laden.
 * @param {number} id
 * @returns {Promise<Object>}
 */
export function holeAutor(id) {
  return get(`/api/authors/${id}`);
}

/**
 * Autor aktualisieren.
 * @param {number} id
 * @param {Object} data
 * @returns {Promise<Object>}
 */
export function aktualisiereAutor(id, data) {
  return patch(`/api/authors/${id}`, data);
}

/**
 * Neuen Autor erstellen.
 * @param {Object} data
 * @returns {Promise<Object>}
 */
export function erstelleAutor(data) {
  return post("/api/authors", data);
}

/**
 * Autor löschen.
 * @param {number} id
 * @returns {Promise<Object>}
 */
export function loescheAutor(id) {
  return del(`/api/authors/${id}`);
}

/**
 * Autor mit Wikipedia/Wikidata anreichern.
 * @param {number} id
 * @returns {Promise<Object>}
 */
export function reichereAutorAn(id) {
  return post(`/api/authors/${id}/anreichern`);
}

/**
 * Angereicherte Daten übernehmen.
 * @param {number} id
 * @param {Object} felder
 * @returns {Promise<Object>}
 */
export function uebernehmAutorenDaten(id, felder) {
  return post(`/api/authors/${id}/anreichern/uebernehmen`, felder);
}

/**
 * Offene Autoren (ohne Wikidata) finden.
 * @returns {Promise<Object>}
 */
export function scanneAutoren() {
  return post("/api/authors/scanner/starten");
}

/**
 * Autoren-Statistik laden.
 * @returns {Promise<Object>}
 */
export function autorenStatistik() {
  return get("/api/authors/statistik/uebersicht");
}

/**
 * Batch-Scan starten (gibt Liste offener Autoren zurück).
 * @returns {Promise<Object>}
 */
export function starteBatchScan() {
  return post("/api/authors/scanner/batch");
}

/**
 * Batch-Scan abbrechen.
 * @returns {Promise<Object>}
 */
export function brecheBatchScanAb() {
  return post("/api/authors/scanner/abbrechen");
}

/**
 * SSE-EventSource für den Batch-Scan.
 * @param {Object} [optionen]
 * @param {boolean} [optionen.nurOhneWikidata=true]
 * @param {boolean} [optionen.autoUebernehmen=false]
 * @param {function} onEvent - Callback pro SSE-Event
 * @param {function} [onError] - Callback bei Fehler
 * @returns {{ close: function }} Controller zum Beenden
 */
export function batchScanEvents(optionen = {}, onEvent, onError) {
  const params = new URLSearchParams();
  const token = getToken();
  params.set("token", token);
  if (optionen.nurOhneWikidata !== false) params.set("nur_ohne_wikidata", "true");
  if (optionen.autoUebernehmen) params.set("auto_uebernehmen", "true");

  const url = `/api/authors/scanner/events?${params.toString()}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent(data);
    } catch {
      // ignorieren
    }
  };

  eventSource.onerror = (e) => {
    eventSource.close();
    if (onError) onError(e);
  };

  return {
    close: () => eventSource.close(),
  };
}

/**
 * Verwaiste Autoren (ohne Bücher) löschen.
 * @returns {Promise<Object>}
 */
export function loescheVerwaiste() {
  return del("/api/authors/verwaist");
}

/**
 * Autoren-Tabelle komplett neu synchronisieren.
 * @returns {Promise<Object>}
 */
export function resyncAutoren() {
  return post("/api/authors/resync");
}

/**
 * Foto-URL für einen Autor.
 * @param {number} id
 * @returns {string}
 */
export function autorenFotoUrl(id, groesse = "normal") {
  const params = new URLSearchParams();
  const token = getToken();
  if (token) params.set("token", token);
  if (groesse !== "normal") params.set("groesse", groesse);
  return `/api/authors/${id}/foto?${params.toString()}`;
}
