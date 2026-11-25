// Letzte Rückfrage vor dem Löschen und Ersetzen: nennt die Folgen, erst ein Ja löst aus

export interface Frage {
  titel: string;
  text?: string;
  folgen?: string[];
  ja: string;
  symbol?: string;
  /** false: nichts geht verloren, der Knopf bleibt ruhig */
  gefahr?: boolean;
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
