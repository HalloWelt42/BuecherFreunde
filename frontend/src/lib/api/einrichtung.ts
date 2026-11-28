// Ersteinrichtung nach einer Neuinstallation (BF-82): Zustand und Schritte, Orte, Anschlüsse, Katalog, Familie, Sicherungen,
// Aufträge, Neuaufbau, Umzug, Wartung und die Einstellungen der Kellerwolke. Formen und Wege nach docs/neubau/SCHNITTSTELLE.md,
// Abschnitt "Ersteinrichtung". Vor dem ersten Konto antworten die Wege ohne Anmeldung, danach nur angemeldet.
import { anfrage, del, get, post, put } from "./client";
import type { Profilangaben } from "./familie";

export type Modus = "neu" | "wartung" | "aus";
export type Lagename = "neu" | "sicherung" | "kellerwolke" | "umzug";
export type Schrittstand = "offen" | "erledigt" | "uebersprungen" | "entfaellt";

export interface Schritt {
  schluessel: string;
  name: string;
  pflicht: boolean;
  stand: Schrittstand;
  /** Was eingerichtet ist oder warum übersprungen, für die Übersicht am Ende */
  text: string;
  /** Ob Weiter geht; sonst steht der Grund da */
  weiter: boolean;
  grund: string;
}

export interface Ausgangslage {
  schluessel: Lagename;
  name: string;
  beschreibung: string;
  schritte: string[];
}

export interface Einrichtung {
  modus: Modus;
  /** Die Oberfläche zeigt den Assistenten: statt der Anmeldung (neu) oder in der Bühne (Wartung) */
  zeigen: boolean;
  ausgangslage: Lagename | null;
  /** Der erste offene Schritt; dort geht es nach einem Neustart weiter */
  schritt: string | null;
  schritte: Schritt[];
  ausgangslagen: Ausgangslage[];
  /** Es gibt ein Konto, mit dem man sich anmelden kann */
  konto: boolean;
  anmeldung: "eigen" | "kellerwolke";
  /** Wartung: so viele Änderungen warten auf die Bestätigung */
  aenderungen: number;
  begonnen_am: string | null;
  abgeschlossen_am: string | null;
}

export interface Ortstand {
  kennung: string;
  name: string;
  pfad: string;
  belegt: number;
  frei: number;
  stand: "gut" | "warn" | "schlecht";
  dauerhaft: boolean;
  marker: boolean;
  text: string;
}

export interface Orte {
  orte: Ortstand[];
  weiter: boolean;
  grund: string;
}

export type Anschlussart = "kellerwolke" | "leitstelle" | "vertonung" | "nachschlag";

export interface Verbindungspruefung {
  ok: boolean;
  text: string;
  grund: string;
  am: string | null;
}

/** Nie der Schlüssel selbst: nur ob einer eingetragen ist */
export interface Schluesselstand {
  eingetragen: boolean;
  herkunft: "app" | "einrichtung" | "";
  /** Ein neuer wartet auf die Bestätigung (Wartung) */
  vorgemerkt: boolean;
}

export interface Anschluss {
  art: Anschlussart;
  name: string;
  adresse: string;
  herkunft: "app" | "einrichtung" | "";
  /** null: dieser Anschluss hat keinen Schlüssel (Nachschlag) */
  schluessel: Schluesselstand | null;
  hinweis: string;
  pruefung: Verbindungspruefung | null;
}

export interface Aenderung {
  id: string;
  schritt: string;
  art: "anschluss" | "katalog" | "profil" | "stimme";
  was: string;
  alt: string;
  neu: string;
}

/** Antwort eines Schritts: auf einer neuen Installation angewandt, unter Wartung nur vorgemerkt */
export interface Vorgemerkt {
  angewandt: boolean;
  aenderung: Aenderung | null;
}

export type Katalogwahl = "standard" | "leer" | "bestand";

export interface Auftragsteil {
  schluessel: string;
  name: string;
  gesamt: number;
  fertig: number;
}

export type Auftragsart = "einspielen" | "pruefung" | "neuaufbau" | "kopieren" | "ligaturen" | "stimmproben" | "texterkennung" | "nachbesserung" | "nachfuehren";

export interface Auftragsstand {
  art: Auftragsart;
  was: string;
  /** leer: noch nie gelaufen */
  stand: "" | "wartet" | "laeuft" | "pause" | "fertig" | "fehler";
  gesamt: number;
  fertig: number;
  teile: Auftragsteil[];
  aktuell: string;
  grund: string;
  begonnen: string | null;
  geaendert: string | null;
  fertig_am: string | null;
}

export type Sicherungsquelle = "datei" | "geraet" | "kellerwolke";

export interface Sicherung {
  quelle: Sicherungsquelle;
  /** Auf dem Gerät der Name, in der Kellerwolke der Knoten, bei einer Datei die Kennung des Hochladens */
  kennung: string;
  name: string;
  groesse: number | null;
  angelegt_am: string | null;
  buecher: number | null;
  profile: number | null;
  version: string;
}

export interface Sicherungsliste {
  quelle: Sicherungsquelle;
  bereit: boolean;
  grund: string;
  sicherungen: Sicherung[];
}

export interface Hochladestand {
  id: string;
  name: string;
  groesse: number;
  sha256: string;
  empfangen: number;
  teil_groesse: number;
  /** Alles da und die Prüfsumme stimmt */
  fertig: boolean;
}

export interface Wiederherstellfolgen {
  sicherung: Sicherung;
  /** Sätze, was ersetzt wird; leer: auf dem Gerät ist noch nichts */
  ersetzt: string[];
  vorher_sichern: boolean;
  stand: string;
}

export interface Wiederherstellstand {
  auftrag: Auftragsstand;
  ergebnis: { name: string; buecher: number; profile: number; version: string; vorher: string } | null;
}

export interface Befund {
  buch_id: number;
  titel: string;
  autor: string;
  ergebnis: "erreichbar" | "wiedergefunden" | "fehlt";
  ort: string;
  pfad: string;
  text: string;
}

export interface Pruefbericht {
  auftrag: Auftragsstand;
  erreichbar: number;
  wiedergefunden: number;
  fehlt: number;
  texte: number;
  /** Wiedergefundene und fehlende; erreichbare stehen nur in der Zahl */
  eintraege: Befund[];
}

export interface Ordnerpruefung {
  pfad: string;
  buecher: number;
  mit_auszug: number;
  ohne_auszug: number;
  mit_persoenlichem: number;
  schon_da: number;
  groesse: number;
  /** Namen aus der Datei der Profile */
  profile: string[];
  profile_datei: boolean;
}

export interface Ohneauszug {
  buch_id: number | null;
  name: string;
  pfad: string;
}

export interface Neuaufbaubericht {
  auftrag: Auftragsstand;
  buecher: number;
  mit_auszug: number;
  ohne_auszug: Ohneauszug[];
  fehler: Ohneauszug[];
  profile: number;
}

export interface Originalort {
  ort: "kellerwolke" | "geraet";
  anzahl: number;
  groesse: number;
}

export interface Umzugsergebnis {
  sicherung: string;
  /** Welche Anschlüsse das alte Gerät nennt */
  einstellungen: string[];
  /** Welche Schlüssel in die Schlüsseldatei kamen, nur die Namen */
  schluessel: string[];
  originale: Originalort;
  einspielen: Auftragsstand;
}

/** Nur in dieser Antwort steht der Code, ein einziges Mal */
export interface UmzugVorbereitet {
  code: string;
  gilt_bis: string;
  sicherung: string;
  groesse: number;
}

export interface Umzugsstand {
  vorbereitet: boolean;
  gilt_bis: string | null;
  versuche_frei: number;
  sicherung: string;
  eingeloest_am: string | null;
  sitzung_bis: string | null;
  gesperrt: boolean;
}

export interface Aenderungen {
  aenderungen: Aenderung[];
  /** Namen der Schritte ohne Änderung */
  unveraendert: string[];
  stand: string;
}

export interface Kellerwolkeneinstellungen {
  persoenlich: boolean;
  sicherungen_ablegen: boolean;
}

export interface Persoenlichfolgen {
  buecher: number;
  profile_datei: string;
  profile: { id: string; name: string; buecher: number }[];
  lesestaende: number;
  vorlesestellen: number;
  notizen: number;
  markierungen: number;
  etiketten: number;
  private: number;
  freigaben: number;
  stand: string;
}

const WEG = "/api/einrichtung";

// Zustand und Schritte
export const ladeEinrichtung = (): Promise<Einrichtung> => get(WEG);
export const waehleAusgangslage = (ausgangslage: Lagename): Promise<Einrichtung> => post(`${WEG}/ausgangslage`, { ausgangslage });
export const setzeSchritt = (schritt: string, aktion: "erledigt" | "ueberspringen"): Promise<Einrichtung> => post(`${WEG}/schritte/${schritt}`, { aktion });
export const schliesseAb = (): Promise<Einrichtung> => post(`${WEG}/abschliessen`);
export const ladeOrte = (): Promise<Orte> => get(`${WEG}/orte`);
export const kontoMitKellerwolke = (adresse: string, schluessel: string): Promise<{ anmeldung: string; app: string; besitzer: string }> =>
  post(`${WEG}/konto/kellerwolke`, { adresse, schluessel });

// Anschlüsse
export const ladeAnschluesse = (): Promise<Anschluss[]> => get(`${WEG}/anschluesse`);
export const pruefeAnschluss = (art: Anschlussart, werte: { adresse?: string; schluessel?: string }): Promise<Verbindungspruefung> =>
  post(`${WEG}/anschluesse/${art}/pruefen`, werte);
export const trageAnschlussEin = (art: Anschlussart, adresse: string, schluessel?: string): Promise<Vorgemerkt> =>
  put(`${WEG}/anschluesse/${art}`, schluessel ? { adresse, schluessel } : { adresse });

// Katalog und Familie
export const waehleKatalog = (wahl: Katalogwahl): Promise<Vorgemerkt> => post(`${WEG}/katalog`, { wahl });
export const legeEinrichtungsprofilAn = (neu: Profilangaben): Promise<Vorgemerkt> => post(`${WEG}/familie/profile`, neu);
export const setzeEinrichtungsstimme = (stimme: string): Promise<Vorgemerkt> => put(`${WEG}/familie/stimme`, { stimme });

// Sicherungen und Wiederherstellen
export const ladeSicherungsliste = (quelle: "geraet" | "kellerwolke"): Promise<Sicherungsliste> => get(`${WEG}/sicherungen`, { quelle });
export const meldeHochladenAn = (name: string, groesse: number, sha256: string): Promise<Hochladestand> =>
  post(`${WEG}/sicherungen/hochladen`, { name, groesse, sha256 });
export const ladeHochladestand = (id: string): Promise<Hochladestand> => get(`${WEG}/sicherungen/hochladen/${id}`);

/** Das nächste Teil ab `ab`; 409 trägt in `data.empfangen` den wahren Stand */
export async function sendeSicherungsteil(id: string, ab: number, teil: Blob, abbruch?: AbortSignal): Promise<Hochladestand> {
  const antwort = await anfrage(`${WEG}/sicherungen/hochladen/${id}`, {
    method: "PATCH",
    body: teil,
    signal: abbruch,
    headers: { "Upload-Offset": String(ab), "Content-Type": "application/octet-stream" },
  });
  return antwort.json();
}

export type Wiederherstellweg = "einrichtung" | "laufend";
const FOLGEN: Record<Wiederherstellweg, string> = { einrichtung: `${WEG}/wiederherstellen/folgen`, laufend: "/api/backup/restore/folgen" };
const BEGINNEN: Record<Wiederherstellweg, string> = { einrichtung: `${WEG}/wiederherstellen`, laufend: "/api/backup/restore" };

/** Was die Sicherung enthält und ersetzt; in der Ersteinrichtung oder auf einer laufenden Installation (Zurückspielen) */
export const ladeWiederherstellfolgen = (weg: Wiederherstellweg, quelle: Sicherungsquelle, kennung: string): Promise<Wiederherstellfolgen> =>
  get(FOLGEN[weg], { quelle, kennung });
export const stelleWiederHer = (weg: Wiederherstellweg, quelle: Sicherungsquelle, kennung: string, stand: string): Promise<Auftragsstand> =>
  post(BEGINNEN[weg], { quelle, kennung, stand });
export const ladeWiederherstellstand = (): Promise<Wiederherstellstand> => get(`${WEG}/wiederherstellen`);

// Aufträge, Prüfung, Neuaufbau
export const ladeAuftraege = (): Promise<Auftragsstand[]> => get(`${WEG}/auftraege`);
export const steuereAuftrag = (art: Auftragsart, aktion: "pause" | "fortsetzen"): Promise<Auftragsstand> => post(`${WEG}/auftraege/${art}/${aktion}`);
export const beginnePruefung = (pruefsummen = false): Promise<Auftragsstand> => post(`${WEG}/pruefung`, { pruefsummen });
export const ladePruefbericht = (): Promise<Pruefbericht> => get(`${WEG}/pruefung/bericht`);
export const PRUEFBERICHT_DATEI = `${WEG}/pruefung/bericht?herunterladen=true`;
export const pruefeOrdner = (pfad: string): Promise<Ordnerpruefung> => post(`${WEG}/neuaufbau/ordner`, { pfad });
export const beginneNeuaufbau = (): Promise<Auftragsstand> => post(`${WEG}/neuaufbau`);
export const ladeNeuaufbaubericht = (): Promise<Neuaufbaubericht> => get(`${WEG}/neuaufbau/bericht`);

// Umzug
export const verbindeUmzug = (adresse: string, code: string): Promise<Umzugsergebnis> => post(`${WEG}/umzug/verbinden`, { adresse, code });
export const waehleOriginale = (weg: "kopieren" | "ort"): Promise<Auftragsstand> => post(`${WEG}/originale`, { weg });
export const bereiteUmzugVor = (): Promise<UmzugVorbereitet> => post("/api/umzug/vorbereiten");
export const ladeUmzug = (): Promise<Umzugsstand> => get("/api/umzug");
export const beendeUmzug = (): Promise<Umzugsstand> => del("/api/umzug");

// Wartung
export const oeffneAssistent = (): Promise<Einrichtung> => post(`${WEG}/oeffnen`);
export const schliesseAssistent = (): Promise<Einrichtung> => post(`${WEG}/schliessen`);
export const ladeAenderungen = (): Promise<Aenderungen> => get(`${WEG}/aenderungen`);
export const uebernimmAenderungen = (stand: string, ids: string[]): Promise<{ uebernommen: Aenderung[]; verworfen: number }> =>
  post(`${WEG}/uebernehmen`, { stand, ids });

// Persönliches in der Kellerwolke
export const ladeKellerwolkeneinstellungen = (): Promise<Kellerwolkeneinstellungen> => get("/api/kellerwolke/einstellungen");
export const setzePersoenlich = (an: boolean, stand: string, entfernen = false): Promise<Kellerwolkeneinstellungen> =>
  put("/api/kellerwolke/einstellungen", { persoenlich: an, stand, entfernen });
export const ladePersoenlichfolgen = (): Promise<Persoenlichfolgen> => get("/api/kellerwolke/persoenlich/folgen");
