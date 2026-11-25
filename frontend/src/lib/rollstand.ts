// Rollhöhe einer Ansicht: beim Zurückkommen steht man wieder dort
const hoehen = new Map<string, number>();

export function rollstand(knoten: HTMLElement, schluessel: string) {
  let jetzt = schluessel;
  const stelle = () => {
    const h = hoehen.get(jetzt) ?? 0;
    knoten.scrollTop = h;
  };
  const merke = () => hoehen.set(jetzt, knoten.scrollTop);
  requestAnimationFrame(stelle);
  knoten.addEventListener("scroll", merke, { passive: true });
  return {
    update(neu: string) {
      if (neu === jetzt) return;
      jetzt = neu;
      requestAnimationFrame(stelle);
    },
    destroy() {
      knoten.removeEventListener("scroll", merke);
    },
  };
}

/** Neuer Inhalt unter derselben Adresse (andere Filter): von oben */
export function vergissRollstand(schluessel: string): void {
  hoehen.delete(schluessel);
}
