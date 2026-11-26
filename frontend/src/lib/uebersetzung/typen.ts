// Bücher übersetzen (BF-71): was die Schnittstelle zeigt und annimmt (docs/neubau/UEBERSETZUNG.md, backend/app/models/fassung.py).
// Zeiten kommen als ISO in Weltzeit (UTC) mit Z.

export type Fassungsstand = "laeuft" | "pause" | "teilweise" | "fertig" | "fehler";
export type Stationsstand = "wartet" | "laeuft" | "fertig";
export type Stationsname = "Zerlegen" | "Begriffe" | "Übersetzen" | "Prüfen" | "Nacharbeit" | "Setzen";
export type Herkunft = "regel" | "ki" | "hand" | "vorgabe";
export type Begriffsart = "begriff" | "einheit";
/** Sprachen, in die übersetzt wird */
export type Zielsprache = "de";
/** Wie das übersetzte Buch den Leser anspricht (englisch "you") */
export type Anrede = "du" | "Sie";

/** Eine Fassung eines Buchs; das Original steht immer zuerst (`id` null) */
export interface Fassungseintrag {
  id: number | null;
  sprache: string;
  original: boolean;
  stand: Fassungsstand;
  kapitel_fertig: number | null;
  kapitel_gesamt: number | null;
  fertig_gegen: string | null;
  modell: string;
  pruefmodell: string;
  angelegt: string;
  geaendert: string;
  /** öffnet "Lesen" auf der Buchseite */
  gewaehlt: boolean;
}

/** Eine Übersetzung im Original gibt es nicht: `id` ist gesetzt */
export type Uebersetzung = Fassungseintrag & { id: number };

export interface Ablageort {
  ort: "kellerwolke" | "geraet";
  pfad: string;
}

/** Rückfrage vor dem Start; `geht` false mit Grund */
export interface Folgen {
  seiten: number;
  kapitel: number;
  bloecke: number;
  begriffe: number;
  abbildungen: number;
  dauer_s: number;
  fertig_gegen: string | null;
  tempo_s_je_seite: number;
  ablage: Ablageort | null;
  geht: boolean;
  grund: string;
  /** Vorgabe der Anrede; fehlt sie, gilt "du" */
  anrede?: Anrede;
}

export interface Station {
  name: Stationsname;
  stand: Stationsstand;
  text: string;
}

export interface Kapitelstand {
  nr: number;
  titel: string;
  stand: Stationsstand;
  /** gemessen, oder (geschaetzt) gemessen und erwartet */
  dauer_s: number;
  geschaetzt: boolean;
  bloecke: number;
  /** mit Ergebnis */
  fertig: number;
  geprueft: number;
  nachgearbeitet: number;
  offen: number;
}

export interface Zahlen {
  bloecke: number;
  uebersetzt: number;
  bestanden: number;
  nachgearbeitet: number;
  offen: number;
}

export interface Laufstand {
  id: number;
  stand: Fassungsstand;
  begonnen: string | null;
  bisher_s: number;
  noch_s: number;
  fertig_gegen: string | null;
  tempo_s_je_seite: number;
  kapitel_jetzt: number | null;
  block_jetzt: string | null;
  stationen: Station[];
  kapitel: Kapitelstand[];
  zahlen: Zahlen;
  grund: string;
}

/** Eine Fassung in Arbeit, für die Aufträge */
export interface Laufeintrag {
  id: number;
  buch_id: number;
  titel: string;
  sprache: string;
  stand: Fassungsstand;
  /** 0 bis 1 */
  anteil: number;
  kapitel_fertig: number;
  kapitel_gesamt: number;
  fertig_gegen: string | null;
  grund: string;
}

export interface Befund {
  art: string;
  quelle: "pruefung" | "ki";
  text: string;
  /** das beanstandete Stück im deutschen Text */
  stelle: string;
}

export interface OffeneStelle {
  kennung: string;
  kapitel: number;
  /** für Menschen, etwa "Getting Started, Absatz 4" */
  ort: string;
  seite_original: number | null;
  /** Vorlage mit Marken */
  original: string;
  /** die letzte Übersetzung mit Marken; leer, wenn keine kam */
  deutsch: string;
  befunde: Befund[];
}

export interface Bericht {
  zahlen: Zahlen;
  offen: OffeneStelle[];
}

export type Blockaktion = { aktion: "neu" } | { aktion: "annehmen" } | { aktion: "setzen"; text: string };

export interface Blockantwort {
  kennung: string;
  stand: string;
  deutsch: string;
  befunde: Befund[];
}

export interface Begriff {
  id: number;
  englisch: string;
  deutsch: string;
  bleibt: boolean;
  herkunft: Herkunft;
  stellen: number;
  grund: string;
  art: Begriffsart;
}

export interface BegriffNeu {
  englisch: string;
  deutsch: string;
  bleibt: boolean;
  grund: string;
  art: Begriffsart;
}

/** Wo man in einer Übersetzung liest, getrennt vom Original */
export interface Fassungslesestand {
  position: string;
  gelesen_am: string | null;
}
