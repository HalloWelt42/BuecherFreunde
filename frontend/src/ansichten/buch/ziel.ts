// Wohin Übernommenes geht (BF-111, Abnahme 1 und 2): beim Bearbeiten ins Formular, gespeichert wird erst mit Speichern
// (formular.svelte.ts); im Kasten "Angaben vergleichen" auf der Buchseite und in "ISBN zur Wahl" gleich ins Buch (hier).
// Werkzeugreihe, ISBN-Suche und Vergleich kennen nur diese Schnittstelle.
import { umschlagNeu, aktualisiereBuch } from "../../lib/api/books";
import { uebernehmVorschlaege } from "../../lib/api/ai";
import { uebernehmMetadaten, type Aktuell, type Vorschlag } from "../../lib/api/metadata";
import { anzahl } from "../../lib/format";
import { bestand } from "../../lib/stand/bestand.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";
import { nutzlast } from "./angaben";

/** Was im Vergleich gewählt ist */
export interface Auswahl {
  vorschlag: Vorschlag;
  /** Kennung der Quelle, "alle" oder "datei" */
  quelle: string;
  /** Schlüssel der gewählten Zeilen (titel, verlag, cover, kategorien, ...) */
  gewaehlt: Set<string>;
  /** Listen aus "Alle Daten", die als Regale dazukommen */
  listen: Set<string>;
}

export interface Angabenziel {
  /** true: gleich ins Buch; false: ins Formular */
  readonly sofort: boolean;
  /** "Bisher" im Vergleich; null: die gespeicherten Angaben, die der Server mitschickt */
  aktuell(): Aktuell | null;
  /** Titel und Autor, gegen die ein Fund geprüft wird; null: die gespeicherten */
  frage(): { titel: string; autor: string } | null;
  /** der Umschlag unter "Bisher", wenn er noch nicht gespeichert ist; null: der gespeicherte */
  bild(): string | null;
  angaben(a: Auswahl): Promise<void>;
  isbn(isbn: string): Promise<void>;
  beschreibung(text: string): Promise<void>;
  /** Regale aus dem Vorschlag der KI */
  regale(namen: string[]): Promise<void>;
  umschlagAusDatei(): Promise<void>;
}

/** Gleich ins Buch, wie der Kasten "Angaben vergleichen" es immer tat; `geaendert` lädt das Buch neu */
export function buchziel(buchId: number, geaendert: () => void): Angabenziel {
  const fertig = (text = "") => {
    if (text) melde.gut(text);
    bestand.geaendert();
    geaendert();
  };
  return {
    sofort: true,
    aktuell: () => null,
    frage: () => null,
    bild: () => null,
    async angaben(a) {
      const e = await uebernehmMetadaten(buchId, nutzlast(a.vorschlag, a.quelle, a.gewaehlt, a.listen));
      if (e.hinweis) melde.warn(`Übernommen, Umschlag nicht: ${e.hinweis}`);
      fertig(e.hinweis ? "" : "Übernommen");      // mit Hinweis steht schon die Warnung da
    },
    async isbn(isbn) {
      await aktualisiereBuch(buchId, { isbn });
      fertig(`ISBN ${isbn} eingetragen`);
    },
    async beschreibung(text) {
      await uebernehmMetadaten(buchId, { beschreibung: text });
      fertig("Beschreibung übernommen");
    },
    async regale(namen) {
      await uebernehmVorschlaege(buchId, namen);
      fertig(`${anzahl(namen.length, "Regal", "Regale")} zugewiesen`);
    },
    async umschlagAusDatei() {
      await umschlagNeu(buchId);
      fertig("Umschlag neu aus der Datei");
    },
  };
}
