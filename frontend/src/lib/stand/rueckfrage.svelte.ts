// Letzte Rückfrage vor dem Löschen und Ersetzen: nennt die Folgen, erst ein Ja löst aus

export interface Frage {
  titel: string;
  text?: string;
  folgen?: string[];
  /** Jede betroffene Datei mit Ort, unter einem gemeinsamen Ordner (Folgenvorschau beim Verwerfen, BF-80) */
  liste?: { titel: string; eintraege: string[] };
  ja: string;
  /** Wie die Taste heißt, die nichts tut; Vorgabe "Abbrechen" */
  nein?: string;
  symbol?: string;
  /** false: nichts geht verloren, der Knopf bleibt ruhig */
  gefahr?: boolean;
  /** Eine Wahl dazu, als Haken unter den Folgen (etwa: vorhandene Dateien in den Papierkorb, BF-82); gilt nur mit Ja */
  wahl?: { text: string; an: boolean; onwahl: (an: boolean) => void };
}

class Rueckfrage {
  offen = $state<Frage | null>(null);
  #antworte: ((ja: boolean) => void) | null = null;

  stelle(frage: Frage): Promise<boolean> {
    this.antworte(false);
    this.offen = frage;
    return new Promise((r) => {
      this.#antworte = r;
    });
  }

  antworte(ja: boolean): void {
    this.#antworte?.(ja);
    this.#antworte = null;
    this.offen = null;
  }
}

export const rueckfrage = new Rueckfrage();

export const frage = (f: Frage): Promise<boolean> => rueckfrage.stelle(f);
