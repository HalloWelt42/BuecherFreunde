// Kurze Hinweise am unteren Rand

export type Meldungsart = "gut" | "schlecht" | "info" | "warn";

export interface Meldung {
  id: number;
  art: Meldungsart;
  text: string;
}

const DAUER: Record<Meldungsart, number> = { gut: 4000, info: 4000, warn: 4500, schlecht: 6000 };
/** So steht ein Fehler ohne Satz des Servers da (lib/api/client.ts); er wird nie als bloße Nummer gezeigt (BF-98) */
const NUR_NUMMER = /^HTTP \d+$/;

/** Ein Fehler als Satz: der Satz des Servers, sonst nach der Art des Fehlers */
export function fehlertext(grund: unknown): string {
  const text = grund instanceof Error ? grund.message : String(grund);
  if (!NUR_NUMMER.test(text)) return text;
  const status = Number((grund as { status?: unknown }).status ?? text.slice(5));
  if (status >= 500) return "Die Bibliothek antwortet gerade nicht. Später erneut versuchen.";
  if (status === 403) return "Das ist für dieses Profil nicht freigegeben.";
  if (status === 404) return "Das gibt es nicht mehr.";
  return "Die Anfrage ging nicht durch.";
}

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
    const text = fehlertext(grund);
    this.#zeige("schlecht", vorab ? `${vorab}: ${text}` : text);
  };

  schliesse(id: number): void {
    this.liste = this.liste.filter((m) => m.id !== id);
  }
}

export const melde = new Meldungen();
