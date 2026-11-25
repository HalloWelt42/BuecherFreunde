// Kurze Hinweise am unteren Rand

export type Meldungsart = "gut" | "schlecht" | "info" | "warn";

export interface Meldung {
  id: number;
  art: Meldungsart;
  text: string;
}

const DAUER: Record<Meldungsart, number> = { gut: 4000, info: 4000, warn: 4500, schlecht: 6000 };

class Meldungen {
  liste = $state<Meldung[]>([]);
  #naechste = 1;

  #zeige(art: Meldungsart, text: string): void {
    const id = this.#naechste++;
    this.liste = [...this.liste, { id, art, text }];
    setTimeout(() => this.schliesse(id), DAUER[art]);
  }

  gut = (text: string) => this.#zeige("gut", text);
  info = (text: string) => this.#zeige("info", text);
  warn = (text: string) => this.#zeige("warn", text);

  /** Nimmt auch Fehler aus der Schnittstelle: ihr Text ist ein deutscher Satz. */
  schlecht = (grund: unknown, vorab = "") => {
    const text = grund instanceof Error ? grund.message : String(grund);
    this.#zeige("schlecht", vorab ? `${vorab}: ${text}` : text);
  };

  schliesse(id: number): void {
    this.liste = this.liste.filter((m) => m.id !== id);
  }
}

export const melde = new Meldungen();
