// Arten und Gattungen, wie der Server sie kennt (BF-59): eine Liste für Angaben, Chips und Bearbeiten, je Sitzung einmal
// geholt. Bis sie da ist, stehen die Kennungen.
import { ladeGattungen, ladeTypen } from "../api/collections";
import type { Art, Gattung } from "../typen";

const BUCH = "Buch";

type Werte = [string, string][];

/** Der gewählte Wert steht immer in der Liste, auch wenn der Server ihn (noch) nicht nennt */
const mitAktuellem = (werte: Werte, aktuell: string): Werte => (werte.some(([w]) => w === aktuell) ? werte : [...werte, [aktuell, aktuell]]);

class Arten {
  typen = $state<Art[]>([]);
  gattungen = $state<Gattung[]>([]);
  #laeuft: Promise<void> | null = null;

  /** Einmal holen; was scheitert, versucht der nächste Aufruf wieder */
  laden(): Promise<void> {
    this.#laeuft ??= Promise.allSettled([ladeTypen(), ladeGattungen()]).then(([typen, gattungen]) => {
      if (typen.status === "fulfilled") this.typen = typen.value;
      if (gattungen.status === "fulfilled") this.gattungen = gattungen.value;
      if (typen.status === "rejected" || gattungen.status === "rejected") this.#laeuft = null;
    });
    return this.#laeuft;
  }

  /** Name der Art; leer heißt Buch */
  typName(id: string): string {
    return id ? (this.typen.find((t) => t.id === id)?.name ?? id) : BUCH;
  }

  gattungName(id: string): string {
    return this.gattungen.find((g) => g.id === id)?.name ?? id;
  }

  /** Für die Auswahl: Buch zuerst, dann die Arten des Servers */
  typWerte(aktuell: string): Werte {
    return mitAktuellem([["", BUCH], ...this.typen.map((t): [string, string] => [t.id, t.name])], aktuell);
  }

  /** Für die Auswahl: keine zuerst, dann die Gattungen des Servers */
  gattungWerte(aktuell: string): Werte {
    return mitAktuellem([["", "keine"], ...this.gattungen.map((g): [string, string] => [g.id, g.name])], aktuell);
  }
}

export const arten = new Arten();
