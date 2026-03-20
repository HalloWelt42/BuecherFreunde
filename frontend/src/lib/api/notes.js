/**
 * API-Modul: Notizen
 */
import { get, post, patch, del } from "./client.js";

export function notizenFuerBuch(bookId) {
  return get(`/api/books/${bookId}/notes`);
}

export function erstelleNotiz(bookId, daten) {
  return post(`/api/books/${bookId}/notes`, daten);
}

export function aktualisiereNotiz(noteId, daten) {
  return patch(`/api/notes/${noteId}`, daten);
}

export function loescheNotiz(noteId) {
  return del(`/api/notes/${noteId}`);
}

export function letzteNotizen(limit) {
  return get("/api/notes/recent", { limit });
}
