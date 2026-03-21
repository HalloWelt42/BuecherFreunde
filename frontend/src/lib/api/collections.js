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

export function buchZuordnen(collectionId, bookId, bandNummer = "") {
  return post(`/api/collections/${collectionId}/buch/${bookId}`, { band_nummer: bandNummer });
}

export function buchAusSammlung(collectionId, bookId) {
  return del(`/api/collections/${collectionId}/buch/${bookId}`);
}

export function ladeTypen() {
  return get("/api/collections/typen");
}
