/**
 * API-Modul: Labels (farbige Lesezeichen)
 */
import { get, post, patch, del } from "./client.js";

export function labelsFuerBuch(bookId) {
  return get(`/api/books/${bookId}/labels`);
}

export function erstelleLabel(bookId, daten) {
  return post(`/api/books/${bookId}/labels`, daten);
}

export function aktualisiereLabel(labelId, daten) {
  return patch(`/api/labels/${labelId}`, daten);
}

export function loescheLabel(labelId) {
  return del(`/api/labels/${labelId}`);
}

export function sucheLabels(q, limit) {
  return get("/api/labels/search", { q, limit });
}
