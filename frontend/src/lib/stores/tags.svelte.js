/**
 * Store: Sammlungen (ersetzt Tags).
 */
import { ladeSammlungen } from "../api/collections.js";

function createSammlungenStore() {
  let sammlungen = $state([]);
  let laden = $state(false);
  let fehler = $state(null);

  return {
    get sammlungen() {
      return sammlungen;
    },
    // Abwärtskompatibel: tags -> sammlungen
    get tags() {
      return sammlungen;
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
        sammlungen = await ladeSammlungen();
      } catch (e) {
        fehler = e.message;
        sammlungen = [];
      } finally {
        laden = false;
      }
    },
  };
}

export const sammlungenStore = createSammlungenStore();
// Abwärtskompatibel
export const tagsStore = sammlungenStore;
