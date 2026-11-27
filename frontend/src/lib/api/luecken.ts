// Lücken in Sammlungen (BF-75, docs/neubau/SCHNITTSTELLE.md, Lücken): je Sprache eine Reihe mit Büchern und fehlenden Bänden,
// die Zahl der Bände, Ausblenden und Zurückholen, die Suchadresse. Alle Wege brauchen die Fähigkeit "luecken".
import { get, patch, post, put } from "./client";
import type { Fundbuch } from "./gutenberg";
import type { Buch } from "../typen";

/** Welche Zahl der Bände gilt: die der Quelle, eine eigene oder ausdrücklich keine */
export type Zahlwahl = "quelle" | "eigene" | "keine";
export type Ausblendgrund = "gibt_es_nicht" | "brauche_ich_nicht";

export interface Luecke {
  sprache: string;
  nummer: number;
  /** aus der Quelle; leer: unbekannt */
  titel: string;
  autor: string;
  isbn: string;
  jahr: number | null;
  /** leer: nur aus den eigenen Nummern */
  quelle: string;
  /** Titel, Autor, Reihe und Band, ISBN als eine Zeile */
  kopieren: string;
  /** die fertige Adresse nach der Vorlage; null ohne Vorlage */
  suchadresse: string | null;
  /** derselbe Band im eigenen Katalog der gemeinfreien Bücher (BF-98), nur lokal abgeglichen */
  gemeinfrei?: Fundbuch | null;
}

export interface Platz {
  art: "buch" | "luecke";
  band: string;
  nummer: number | null;
  zwischen: boolean;
  buch_id: number | null;
  buch: Buch | null;
  luecke: Luecke | null;
}

export interface Nachschlagen {
  stand: "offen" | "fertig" | "fehler" | "nicht";
  quelle: string;
  quelle_name: string;
  reihe: string;
  grund: string;
  am: string | null;
}

export interface Reihe {
  /** Kürzel; leer: kein Buch nennt eine Sprache */
  sprache: string;
  name: string;
  /** Name der Reihe in dieser Sprache */
  reihe: string;
  gesamt: number | null;
  herkunft: Zahlwahl | "";
  quelle_gesamt: number | null;
  eigene: number | null;
  nachschlagen: Nachschlagen;
  buecher: number;
  belegt: number;
  fehlen: number[];
  /** etwa "es fehlen 4, 9, 11 und 12"; leer ohne Lücke */
  zeile: string;
  eintraege: Platz[];
}

export interface Ausgeblendet {
  sprache: string;
  name: string;
  nummer: number;
  grund: Ausblendgrund;
  grund_text: string;
  titel: string;
  am: string;
}

export interface Sammlungsluecken {
  sammlung_id: number;
  name: string;
  autor: string;
  /** Platzhalter im Regal */
  an: boolean;
  reihen: Reihe[];
  ausgeblendet: Ausgeblendet[];
}

export interface Gesamtangabe {
  sprache: string;
  wahl: Zahlwahl;
  zahl?: number;
}

export interface Suchadresseinstellungen {
  /** leer: keine Suche, im Feld nur Kopieren */
  suchadresse: string;
  platzhalter: { name: string; bedeutung: string }[];
}

export interface Suchprobe {
  adresse: string | null;
  sammlung: string;
  luecke: Luecke | null;
}

const weg = (sammlung: number) => `/api/collections/${sammlung}/luecken`;

export const ladeLuecken = (sammlung: number): Promise<Sammlungsluecken> => get(weg(sammlung));
/** Platzhalter an oder aus und je Sprache die Zahl der Bände */
export const aendereLuecken = (sammlung: number, aenderung: { an?: boolean; gesamt?: Gesamtangabe[] }): Promise<Sammlungsluecken> => patch(weg(sammlung), aenderung);
export const blendeLueckeAus = (sammlung: number, sprache: string, nummer: number, grund: Ausblendgrund): Promise<Sammlungsluecken> => post(`${weg(sammlung)}/ausblenden`, { sprache, nummer, grund });
export const holeLueckeZurueck = (sammlung: number, sprache: string, nummer: number): Promise<Sammlungsluecken> => post(`${weg(sammlung)}/zurueckholen`, { sprache, nummer });
export const schlageLueckenNach = (sammlung: number): Promise<Sammlungsluecken> => post(`${weg(sammlung)}/nachschlagen`);

export const ladeSuchadresse = (): Promise<Suchadresseinstellungen> => get("/api/luecken/einstellungen");
export const speichereSuchadresse = (suchadresse: string): Promise<Suchadresseinstellungen> => put("/api/luecken/einstellungen", { suchadresse });
/** Die fertige Adresse mit dieser Vorlage für einen fehlenden Band, den das Profil sieht; merkt nichts */
export const probiereSuchadresse = (suchadresse: string): Promise<Suchprobe> => post("/api/luecken/suchadresse/probe", { suchadresse });
