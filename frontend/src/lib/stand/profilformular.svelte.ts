// Welches Profil gerade im Fenster bearbeitet wird (BF-78): aus dem Kopf das eigene, im Elternbereich jedes, das man ändern
// darf, oder ein neues. Das Fenster steht einmal in der Schale; wer es öffnet, ruft nur `oeffne`.
import type { Profil, Rolle } from "../api/familie";

export type Formularziel = { profil: Profil } | { neu: Rolle };

class Profilformularstand {
  offen = $state<Formularziel | null>(null);
  /** Wer nach dem Anlegen ein neues Profil zeigen will (Elternbereich) */
  #nachAnlegen: ((p: Profil) => void) | null = null;

  oeffne(ziel: Formularziel, nachAnlegen: ((p: Profil) => void) | null = null): void {
    this.offen = ziel;
    this.#nachAnlegen = nachAnlegen;
  }

  angelegt(p: Profil): void {
    this.#nachAnlegen?.(p);
  }

  schliesse(): void {
    this.offen = null;
    this.#nachAnlegen = null;
  }
}

export const profilformular = new Profilformularstand();
