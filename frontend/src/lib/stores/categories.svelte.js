/**
 * Store: Kategorien (flache Liste).
 */
import { ladeKategorien } from "../api/categories.js";

function createCategoriesStore() {
  let kategorien = $state([]);
  let laden = $state(false);
  let fehler = $state(null);

  return {
    get kategorien() {
      return kategorien;
    },
    get laden() {
      return laden;
    },
    get fehler() {
      return fehler;
    },

    async aktualisieren() {
      laden = true;
      fehler = null;
      try {
        const alle = await ladeKategorien();
        // Spezial-Kategorien oben, dann alphabetisch
        kategorien = alle.sort((a, b) => {
          if (a.spezial && !b.spezial) return -1;
          if (!a.spezial && b.spezial) return 1;
          return (a.name || "").localeCompare(b.name || "", "de");
        });
      } catch (e) {
        fehler = e.message;
        kategorien = [];
      } finally {
        laden = false;
      }
    },
  };
}

export const categoriesStore = createCategoriesStore();
