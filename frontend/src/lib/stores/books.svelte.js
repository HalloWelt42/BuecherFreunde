/**
 * Store: Bücher mit Filtern und Nachladen.
 */
import { listeBooks } from "../api/books.js";

function createBooksStore() {
  let books = $state([]);
  let total = $state(0);
  let laden = $state(false);
  let fehler = $state(null);
  let seite = $state(1);
  let filter = $state({
    pro_seite: 48,
    sortierung: "titel",
    richtung: "asc",
    kategorie: null,
    tag: null,
    sammlung: null,
    favorit: null,
    zu_lesen: null,
    bewertung_min: null,
    format: null,
    gelesen: null,
    hat_isbn: null,
    weiterlesen: null,
  });

  function buildParams() {
    const params = { seite, ...filter };
    // Nur gesetzte Filter senden
    const clean = {};
    for (const [key, val] of Object.entries(params)) {
      if (val !== null && val !== undefined && val !== "") {
        clean[key] = val;
      }
    }
    return clean;
  }

  return {
    get books() { return books; },
    get total() { return total; },
    get laden() { return laden; },
    get fehler() { return fehler; },
    get filter() { return filter; },

    setFilter(neueFilter) {
      // Komplett ersetzen statt mergen - verhindert veraltete Filterwerte
      filter = {
        pro_seite: neueFilter.pro_seite ?? filter.pro_seite ?? 48,
        sortierung: neueFilter.sortierung ?? "titel",
        richtung: neueFilter.richtung ?? "asc",
        kategorie: neueFilter.kategorie ?? null,
        tag: neueFilter.tag ?? null,
        sammlung: neueFilter.sammlung ?? null,
        favorit: neueFilter.favorit ?? null,
        zu_lesen: neueFilter.zu_lesen ?? null,
        bewertung_min: neueFilter.bewertung_min ?? null,
        format: neueFilter.format ?? null,
        gelesen: neueFilter.gelesen ?? null,
        hat_isbn: neueFilter.hat_isbn ?? null,
        weiterlesen: neueFilter.weiterlesen ?? null,
      };
      seite = 1;
      // books nicht leeren - verhindert Scroll-Jump
      this.laden_();
    },

    async laden_() {
      laden = true;
      fehler = null;
      try {
        const result = await listeBooks(buildParams());
        const neueBuecher = result.buecher || result.books || [];
        if (seite === 1) {
          books = neueBuecher;
        } else {
          books = [...books, ...neueBuecher];
        }
        total = result.gesamt ?? result.total ?? 0;
      } catch (e) {
        fehler = e.message;
        if (seite === 1) {
          books = [];
          total = 0;
        }
      } finally {
        laden = false;
      }
    },

    async mehrLaden() {
      if (books.length >= total || laden) return;
      seite += 1;
      await this.laden_();
    },
  };
}

export const booksStore = createBooksStore();
