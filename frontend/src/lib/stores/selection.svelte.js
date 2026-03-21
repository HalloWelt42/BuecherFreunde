/**
 * Store: Buchauswahl für Massenbearbeitung.
 */

function createSelectionStore() {
  let selected = $state(new Set());
  let active = $state(false);

  return {
    get selected() { return selected; },
    get count() { return selected.size; },
    get active() { return active; },
    get ids() { return [...selected]; },

    toggle(id) {
      const next = new Set(selected);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      selected = next;
      active = selected.size > 0;
    },

    add(id) {
      if (!selected.has(id)) {
        const next = new Set(selected);
        next.add(id);
        selected = next;
        active = true;
      }
    },

    addRange(ids) {
      const next = new Set(selected);
      for (const id of ids) {
        next.add(id);
      }
      selected = next;
      active = selected.size > 0;
    },

    remove(id) {
      if (selected.has(id)) {
        const next = new Set(selected);
        next.delete(id);
        selected = next;
        active = selected.size > 0;
      }
    },

    has(id) {
      return selected.has(id);
    },

    selectAll(ids) {
      selected = new Set(ids);
      active = selected.size > 0;
    },

    clear() {
      selected = new Set();
      active = false;
    },
  };
}

export const selectionStore = createSelectionStore();
