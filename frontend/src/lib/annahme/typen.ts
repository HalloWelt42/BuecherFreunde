// Ein Eintrag der Annahme, so wie der Server ihn führt (docs/neubau/SCHNITTSTELLE.md)

export type Annahmestand =
  | "wartet" | "laedt" | "angehalten" | "liest" | "angaben" | "entpacken" | "bestaetigen" | "regal" | "wissen" | "fertig" | "ohne_text" | "da"
  | "entpackt" | "format" | "kaputt" | "fehler" | "verworfen";

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
  /** Die Vorschau, zu der die Aufnahme gehört (BF-80); leer: ohne Halt vor dem Regal */
  vorschau?: string | null;
  /** Die Aufnahme der ZIP, aus der sie stammt */
  teil_von?: number | null;
  /** Begleitmaterial zu diesem Buch (BF-81) */
  material_fuer?: number | null;
}

export interface AnnahmeZaehler {
  alle: number;
  laeuft: number;
  /** Warten vor dem Regal auf die Bestätigung (BF-80) */
  bestaetigen?: number;
  klaeren: number;
  da: number;
  fertig: number;
}

/** Zahlen je Quelle über alle sichtbaren Einträge, nicht nur über die gelieferten */
export interface Quellenzahlen {
  gesamt: number;
  laeuft: number;
  bestaetigen?: number;
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
  /** Die offenen Vorschauen, die auf die Bestätigung warten ("Zum Bestätigen", BF-80) */
  vorschauen?: Vorschaukurz[];
}

/** Eine Vorschau vor dem Übernehmen, kurz (BF-80, docs/neubau/SCHNITTSTELLE.md) */
export interface Vorschaukurz {
  id: string;
  name: string;
  quelle: Annahmequelle;
  stand: "offen" | "uebernommen" | "verworfen";
  /** ohne die ZIP selbst */
  dateien: number;
  /** stehen auf "bestaetigen" */
  warten: number;
  /** werden noch hochgeladen, gelesen oder ausgepackt */
  laeuft: number;
  /** prüft die KI noch */
  ki: number;
  groesse: number;
  /** nach dem Übernehmen, etwa "3 Dateien blieben im Eingang" */
  hinweis: string;
  angelegt_am: string;
  geaendert_am: string;
}

/**
 * Wohin eine Datei aus dem Browser geht: in eine Vorschau (Hochladen, BF-80), ohne Vorschau bekommt jede Datei ihre eigene;
 * oder als Begleitmaterial zu einem Buch (BF-81), eine ZIP auf Wunsch ausgepackt.
 */
export type Annahmeziel = { art: "vorschau"; vorschau: string | null; anreichern: boolean } | { art: "material"; buch: number; entpacken: boolean };

export interface NeueDatei {
  name: string;
  groesse: number;
  sha256: string;
  ziel: Annahmeziel;
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
  ziel: Annahmeziel;
}
