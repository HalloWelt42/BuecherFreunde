// Ein Sprecher spricht Text Satz für Satz mit einer seiner Stimmen. Welche es gibt, entscheidet, was angeschlossen ist.

export interface Stimme {
  /** Sprecher und Stimme, etwa "dienst:abc" oder "geraet:Anna" */
  id: string;
  name: string;
  gruppe: string;
}

/** Ein Satz und seine Lage im Text, aus dem er stammt */
export interface Satz {
  text: string;
  von: number;
  bis: number;
}

export interface Tonsatz extends Satz {
  /** Fertiger Ton; null, wenn der Sprecher erst beim Spielen spricht */
  ton: Blob | null;
  /** Dauer in Sekunden, geschätzt, wo kein Ton vorliegt */
  dauer: number;
}

export interface Sprecher {
  /** Noch im Tippen rufen, sonst bleibt der Ton am Telefon stumm. */
  entsperre(): void;
  /** Die Sätze des Textes in Lesefolge, jeder, sobald er bereit ist */
  saetze(text: string, stimme: string, abbruch: AbortSignal): AsyncIterable<Tonsatz>;
  /** Spielt einen Satz bis zum Ende; `halt` beendet ihn vorzeitig, ebenfalls ohne Fehler. */
  spiele(satz: Tonsatz, stimme: string, fortschritt: (anteil: number) => void): Promise<void>;
  pause(): void;
  weiter(): void;
  halt(): void;
  tempo: number;
}

// Vorgelesen wird aus einer Lesequelle: das Buch als Folge von Einheiten (Seiten, Kapitel, Stücke). Der Text kommt erst, wenn
// er gebraucht wird.

export interface Stelle {
  einheit: number;
  zeichen: number;
}

/** bis: ausschließlich; null heißt bis zum Ende des Buchs */
export interface Strecke {
  von: Stelle;
  bis: Stelle | null;
}

export interface Satzort {
  einheit: number;
  von: number;
  bis: number;
}

export interface Lesequelle {
  readonly anzahl: number;
  name(einheit: number): string;
  text(einheit: number): Promise<string>;
  /** Hebt den Satz hervor; null nimmt die Hervorhebung weg */
  markiere(ort: Satzort | null): void;
  /** Bringt die Stelle ruhig in den Blick; sofort: ohne Übergang, auch von weit her */
  fuehre(stelle: Stelle, sofort: boolean): Promise<void>;
  sichtbar(ort: Satzort): boolean;
  /** Ende des Kapitels, in dem die Stelle liegt; null ohne Verzeichnis */
  kapitelende(stelle: Stelle): Promise<Stelle | null>;
}

/** Ein Buch im Leser: dazu, wo man gerade liest, was der Schirm zeigt und das Kapitel darum */
export interface Buchquelle extends Lesequelle {
  hier(): Promise<Stelle>;
  /** Was der Schirm zeigt (beim PDF die Seite) */
  seite(): Promise<Strecke>;
  kapitel(): Promise<Strecke | null>;
  readonly mitKapiteln: boolean;
  /** Wie eine Einheit heißt, für die Schlafuhr */
  readonly einheitsart: "Seite" | "Abschnitt" | "Stück";
}
