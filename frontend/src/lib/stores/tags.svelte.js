/**
 * Store: Tags.
 */
import { ladeTags } from "../api/tags.js";

function createTagsStore() {
  let tags = $state([]);
  let laden = $state(false);
  let fehler = $state(null);

  return {
    get tags() {
      return tags;
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
        tags = await ladeTags();
      } catch (e) {
        fehler = e.message;
        tags = [];
      } finally {
        laden = false;
      }
    },
  };
}

export const tagsStore = createTagsStore();
