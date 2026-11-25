// Rollhöhe einer Ansicht: beim Zurückkommen steht man wieder dort, Neues beginnt oben
const hoehen = new Map<string, number>();

export function rollstand(knoten: HTMLElement, schluessel: string) {
  let jetzt = schluessel;
  let stellt = false;

  // Das Ziel wird sofort gelesen: Umbauten im Inhalt verschieben die Höhe noch vor dem nächsten Bild und würden sonst
  // unter dem neuen Schlüssel gemerkt
  const stelle = () => {
    const ziel = hoehen.get(jetzt) ?? 0;
    stellt = true;
    knoten.scrollTop = ziel;
    requestAnimationFrame(() => {
      knoten.scrollTop = ziel;
      stellt = false;
    });
  };
  const merke = () => {
    if (!stellt) hoehen.set(jetzt, knoten.scrollTop);
  };

  stelle();
  knoten.addEventListener("scroll", merke, { passive: true });
  return {
    update(neu: string) {
      if (neu === jetzt) return;
      jetzt = neu;
      stelle();
    },
    destroy() {
      knoten.removeEventListener("scroll", merke);
    },
  };
}

/** Neuer Inhalt unter derselben Adresse (andere Suche oder Sortierung): von oben */
export function vergissRollstand(schluessel: string): void {
  hoehen.delete(schluessel);
}
