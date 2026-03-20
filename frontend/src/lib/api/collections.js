/**
 * API-Modul: Sammlungen
 */
import { get, post, patch, del } from "./client.js";

export function ladeSammlungen() {
  return get("/api/collections");
}

export function holeSammlung(id) {
  return get(`/api/collections/${id}`);
}

export function erstelleSammlung(daten) {
  return post("/api/collections", daten);
}

export function aktualisiereSammlung(id, daten) {
  return patch(`/api/collections/${id}`, daten);
}

export function loescheSammlung(id) {
  return del(`/api/collections/${id}`);
}

export function buchHinzufuegen(collectionId, bookId) {
  return post(`/api/collections/${collectionId}/books/${bookId}`);
}

export function buchEntfernen(collectionId, bookId) {
  return del(`/api/collections/${collectionId}/books/${bookId}`);
}
