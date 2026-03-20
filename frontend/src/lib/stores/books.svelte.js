/**
 * Store: Bücher mit Pagination und Filtern.
 */
import { listeBooks } from "../api/books.js";

function createBooksStore() {
  let books = $state([]);
  let total = $state(0);
  let laden = $state(false);
  let fehler = $state(null);
  let filter = $state({
    limit: 50,
    offset: 0,
    sort_by: "title",
    sort_dir: "asc",
    category_id: null,
    tag_id: null,
    is_favorite: null,
    is_to_read: null,
    min_rating: null,
    file_format: null,
    search: null,
  });

  return {
    get books() {
      return books;
    },
    get total() {
      return total;
    },
    get laden() {
      return laden;
    },
    get fehler() {
      return fehler;
    },
    get filter() {
      return filter;
    },

    setFilter(neueFilter) {
      filter = { ...filter, ...neueFilter, offset: 0 };
      this.laden_();
    },

    naechsteSeite() {
      if (filter.offset + filter.limit < total) {
        filter = { ...filter, offset: filter.offset + filter.limit };
        this.laden_();
      }
    },

    vorherigeSeite() {
      if (filter.offset > 0) {
        filter = {
          ...filter,
          offset: Math.max(0, filter.offset - filter.limit),
        };
        this.laden_();
      }
    },

    async laden_() {
      laden = true;
      fehler = null;
      try {
        const result = await listeBooks(filter);
        books = result.books;
        total = result.total;
      } catch (e) {
        fehler = e.message;
        books = [];
        total = 0;
      } finally {
        laden = false;
      }
    },
  };
}

export const booksStore = createBooksStore();
