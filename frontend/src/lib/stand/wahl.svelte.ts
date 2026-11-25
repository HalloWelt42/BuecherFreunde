// Das gewählte Buch: steht rechts in der Vorschau und färbt das Licht hinter dem Glas
import type { Buch } from "../typen";
import type { Dreiklang } from "../farben";
import { VORGABE } from "../palette";

class Wahl {
  buch = $state<Buch | null>(null);
  #farben = $state<Record<number, Dreiklang>>({});

  licht = $derived<Dreiklang>((this.buch && this.#farben[this.buch.id]) || VORGABE[0]);

  waehle(buch: Buch): void {
    this.buch = buch;
  }

  /** Nur setzen, wenn noch nichts gewählt ist (erste Liste der Sitzung) */
  falls(buch: Buch | undefined): void {
    if (buch && !this.buch) this.buch = buch;
  }

  kenntFarben(id: number): boolean {
    return id in this.#farben;
  }

  merkeFarben(id: number, farben: Dreiklang): void {
    this.#farben[id] = farben;
  }

  /** Änderungen an einem Buch (Favorit, Sterne) auch in der Vorschau zeigen */
  aktualisiere(id: number, neu: Partial<Buch>): void {
    if (this.buch?.id === id) this.buch = { ...this.buch, ...neu };
  }
}

export const wahl = new Wahl();
