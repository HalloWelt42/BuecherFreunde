// Ein Eintrag der Annahme, so wie der Server ihn führt (docs/neubau/SCHNITTSTELLE.md)

export type Annahmestand = "wartet" | "laedt" | "angehalten" | "liest" | "angaben" | "regal" | "wissen" | "fertig" | "ohne_text" | "da" | "format" | "kaputt" | "fehler";

/** Woher die Datei kommt: Browser, Eingangsordner der Kellerwolke, Einlese-Ordner, externe Sammlung, gemeinfreie Bücher */
export type Annahmequelle = "hochladen" | "eingangsordner" | "ordner" | "extern" | "gemeinfrei";

export interface AnnahmeEintrag {
  id: number;
  name: string;
  groesse: number;
  sha256: string;
  empfangen: number;
  teil_groesse: number;
  stand: Annahmestand;
  schritt: number;
  anteil: number;
  text: string;
  buch_id: number | null;
  quelle: Annahmequelle;
  angelegt_am: string;
  geaendert_am: string;
}

export interface AnnahmeZaehler {
  alle: number;
  laeuft: number;
  klaeren: number;
  da: number;
  fertig: number;
}

/** Zahlen je Quelle über alle sichtbaren Einträge, nicht nur über die gelieferten */
export interface Quellenzahlen {
  gesamt: number;
  laeuft: number;
  fertig: number;
  da: number;
  gescheitert: number;
}

export interface AnnahmeListe {
  /** Die neuesten, höchstens 300 */
  eintraege: AnnahmeEintrag[];
  /** Wie viele es darüber hinaus gibt */
  weitere?: number;
  zaehler: AnnahmeZaehler;
  quellen?: Partial<Record<Annahmequelle, Quellenzahlen>>;
}

export interface NeueDatei {
  name: string;
  groesse: number;
  sha256: string;
  /** Nach dem Eintragen Angaben aus Verzeichnissen holen */
  anreichern: boolean;
}

/** Was der Hochlader vom Server braucht; im Test durch nachgebaute Antworten ersetzt. */
export interface AnnahmeDienst {
  anlegen(datei: NeueDatei): Promise<AnnahmeEintrag>;
  stand(id: number): Promise<AnnahmeEintrag>;
  teil(id: number, ab: number, inhalt: Blob, abbruch: AbortSignal): Promise<AnnahmeEintrag>;
}

/** Der Server steht an einer anderen Stelle als gedacht (409) */
export class AndererStand extends Error {
  constructor(public empfangen: number) {
    super("Der Server steht an einer anderen Stelle");
  }
}

/** Kein Netz oder der Server antwortet gerade nicht: später von selbst weiter */
export class OhneVerbindung extends Error {}

export type Lage = "ansteht" | "prueft" | "laedt" | "angehalten" | "ohne_verbindung" | "beim_server" | "fehler";

/** Eine Datei, die dieser Browser gerade bearbeitet */
export interface Hochladung {
  schluessel: string;
  name: string;
  groesse: number;
  lage: Lage;
  /** Anteil der Prüfsumme (prueft) oder des Hochladens (laedt) */
  anteil: number;
  gesendet: number;
  text: string;
  eintrag: AnnahmeEintrag | null;
}
