/**
 * API-Modul: Textmarkierungen (Highlights) mit optionalen Label-Feldern
 */
import { get, post, patch, del } from "./client.js";

export function highlightsFuerBuch(bookId) {
  return get(`/api/books/${bookId}/highlights`);
}

export function erstelleHighlight(bookId, daten) {
  return post(`/api/books/${bookId}/highlights`, daten);
}

export function loescheHighlight(highlightId) {
  return del(`/api/highlights/${highlightId}`);
}

export function aktualisiereHighlight(highlightId, daten) {
  return patch(`/api/highlights/${highlightId}`, daten);
}
