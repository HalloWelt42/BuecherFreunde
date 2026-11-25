// Angaben aus Verzeichnissen und aus dem Buchtext; Stand der Quellen
import { get, post } from "./client";

/** Angaben einer Quelle zu einem Buch, wie sie der Vergleich zeigt */
export interface Vorschlag {
  titel?: string;
  untertitel?: string;
  autor?: string;
  verlag?: string;
  jahr?: number | string | null;
  seiten?: number | string | null;
  isbn?: string;
  sprache?: string;
  beschreibung?: string;
  cover_url?: string;
  kategorien?: string[];
  quelle?: string;
  /** worüber gefunden: ISBN, DOI oder Titel und Autor */
  fund?: "isbn" | "doi" | "titel" | "";
  /** bei Titelsuche: Titel und Autor stimmen genau */
  sicher?: boolean;
  /** Feld -> Kennung der Quelle */
  herkunft?: Record<string, string>;
  raw?: Record<string, unknown>;
}

export interface Aktuell extends Vorschlag {
  hat_cover?: boolean;
}

export type Quellenart = "buch" | "autor" | "bestand";

/** Gemerkter Stand einer Quelle; gefragt wird sie dabei nicht */
export interface Quellenstand {
  kennung: string;
  name: string;
  anbieter: string;
  art: Quellenart;
  adresse: string;
  aktiv: boolean;
  /** eingeschaltet und, falls nötig, mit eigenem Schlüssel */
  bereit: boolean;
  erreichbar: boolean;
  stand: "gut" | "warn" | "schlecht" | "aus";
  wort: string;
  grund: string;
  anfragen_heute: number;
  hintergrund_heute: number;
  tagesgrenze: number;
  gemerkt: number;
  gemerkt_bytes: number;
}

export interface Angabensuche {
  angereichert: boolean;
  grund?: string;
  quelle?: string;
  vorschlag?: Vorschlag;
  aktuell?: Aktuell;
  /** Quellen, die gerade nicht antworten, mit Grund */
  hinweise?: string[];
}

export interface Angabenuebernahme {
  uebernommen: boolean;
  felder: string[];
  kategorien_erstellt: number;
  cover_gespeichert: boolean;
  hinweis: string;
}

export const sucheMetadaten = (buch: number, quelle?: string): Promise<Angabensuche> => post(`/api/metadata/buch/${buch}/anreichern${quelle ? `?quelle=${quelle}` : ""}`);
export const uebernehmMetadaten = (buch: number, daten: Record<string, unknown>): Promise<Angabenuebernahme> => post(`/api/metadata/buch/${buch}/uebernehmen`, daten);
export const ladeVolltext = (buch: number, von = 1, bis = 5): Promise<any> => get(`/api/metadata/buch/${buch}/volltext`, { seite_von: von, seite_bis: bis });
export const ladeQuellen = (): Promise<Quellenstand[]> => get("/api/metadata/quellen");
/** Echte Probe, je Quelle höchstens einmal in der Minute */
export const pruefeQuelle = (kennung: string): Promise<Quellenstand> => post(`/api/metadata/quellen/${kennung}/pruefen`);
