// Familie mit Profilen (BF-78, docs/neubau/FAMILIE.md): Profile, Wahl beim Start, Rechte, Freigaben, Lesezeit, Einblick,
// Katze. Was ein Profil sieht und darf, entscheidet der Server; die Oberfläche zeigt nur, was er erlaubt.
import { del, get, patch, post, put } from "./client";
import type { Buch } from "../typen";

export type Rolle = "verwaltung" | "erwachsen" | "kind";
export type Stufe = "vorlesen" | "erstes_lesen" | "lesen_lernen" | "schule" | "jugend";

/** Was ein Profil darf, aus Rolle und Stufe (stufen.json am Server) */
export type Faehigkeit =
  | "lesen" | "vorlesen" | "lesezeichen" | "suche" | "favoriten" | "markierungen" | "notizen" | "etiketten" | "sammeln"
  | "hinzufuegen" | "bearbeiten" | "loeschen" | "einstellungen" | "profile" | "freigeben" | "ki";

/** Schrift des Kindes, ausgehend von der Größe seiner Stufe */
export type Schriftgroesse = "klein" | "mittel" | "gross";

export interface Lesehilfen {
  /** Vorlesen mit Mitlesen: das gelesene Wort leuchtet */
  mitlesen: boolean;
  /** Tempo des Vorlesens, 1 ist normal */
  tempo: number;
  /** Farbige Silben; das Kind schaltet sie selbst an und aus */
  silben: boolean;
  lesezeile: boolean;
  schrift: Schriftgroesse;
}

export interface Lesezeitregel {
  /** false: keine Grenze am Tag */
  an: boolean;
  minuten: number;
  /** Ruhezeit, etwa eine Stunde vor dem Schlafen bis zum Morgen */
  ruhe_an: boolean;
  /** "19:30" */
  ruhe_von: string;
  ruhe_bis: string;
  vorlesen_zaehlt: boolean;
}

export interface Katze {
  an: boolean;
  name: string;
  schnurren: boolean;
}

export interface Profileinstellungen {
  lesehilfen: Lesehilfen;
  lesezeit: Lesezeitregel;
  katze: Katze;
}

/** Ein Profil, ohne Geheimnisse */
export interface Profil {
  /** UUID */
  id: string;
  name: string;
  /** Symbol aus Font Awesome, leer: ohne */
  zeichen: string;
  farbe: string;
  rolle: Rolle;
  /** Nur bei Kindern */
  stufe: Stufe | null;
  hat_pin: boolean;
  hat_bild_pin: boolean;
  /** Nur für die, die das Profil ändern dürfen */
  geburtsjahr?: number | null;
  einstellungen?: Partial<Profileinstellungen>;
}

/** GET /api/familie */
export interface Familie {
  profile: Profil[];
  /** Ohne gültigen Profilschlüssel und mit mehr als einem Profil oder einer PIN: erst wählen */
  braucht_wahl: boolean;
  geraet: { gebunden_an: string | null };
}

export interface Lesezeitstand {
  heute_s: number;
  /** null: ohne Grenze */
  rest_s: number | null;
  ruht: boolean;
  /** Bis wann die Ruhezeit gilt, "07:00" */
  ruhe_bis: string | null;
  /** Ab so viel Lesezeit heute kommt der sanfte Hinweis */
  hinweis_ab_s: number | null;
}

/** Darstellung des Kinderbereichs nach Stufe und Lesehilfen */
export interface Kinddarstellung {
  schrift?: string;
  groesse_px?: number;
  woerter_je_zeile?: number | null;
  tippflaeche_px?: number;
}

/** GET /api/familie/ich: das aktive Profil mit allem, was die Oberfläche braucht */
export interface Ich {
  profil: Profil;
  faehigkeiten: Faehigkeit[];
  darstellung: Kinddarstellung;
  lesezeit: Lesezeitstand;
  katze: Katze;
}

/** Was die Eltern im Einblick sehen */
export type Einblickart = "titel" | "lesezeit" | "fortschritt" | "grober_fortschritt" | "geteiltes";

/** Eine Stufe aus stufen.json */
export interface Stufenangabe {
  schluessel: Stufe;
  name: string;
  /** Alter in Jahren, für den Vorschlag aus dem Geburtsjahr */
  alter_von: number;
  /** null: nach oben offen */
  alter_bis: number | null;
  faehigkeiten: Faehigkeit[];
  einblick: Einblickart[];
  vorgaben?: Partial<Profileinstellungen>;
}

/** Vorgabe der Lesezeit am Tag nach Alter */
export interface Lesezeitvorgabe {
  alter_von: number;
  alter_bis: number | null;
  minuten: number;
}

/** GET /api/familie/stufen */
export interface Stufen {
  stufen: Stufenangabe[];
  lesezeit: Lesezeitvorgabe[];
}

/** Antwort auf die Wahl: der Schlüssel für X-Profil und das Profil samt Rechten */
export interface Wahl {
  schluessel: string;
  profil: Ich;
}

/** Was mit einem Profil verloren geht */
export interface Profilfolgen {
  notizen: number;
  markierungen: number;
  etiketten: number;
  lesestaende: number;
  freigaben: number;
  private_buecher: number;
}

export interface Freigabekategorie {
  id: number;
  name: string;
  zeichen: string;
  anzahl: number;
}

/** GET /api/familie/profile/{id}/freigaben; buecher sind die einzeln freigegebenen */
export interface Freigaben {
  kategorien: Freigabekategorie[];
  buecher: Buch[];
}

export type Freigabeart = "buch" | "kategorie";

export interface Einblickeintrag {
  buch: Pick<Buch, "id" | "title"> & Partial<Buch>;
  /** Anteil 0 bis 1; ab Schule nur grob */
  fortschritt: number;
  seite?: number;
  seiten?: number;
  lesezeit_heute_s?: number;
  zuletzt?: string | null;
}

export interface Einblick {
  eintraege: Einblickeintrag[];
  sichtbar: Einblickart[];
}

/** Womit sich jemand ausweist: PIN aus Ziffern oder drei Bildschlüssel */
export type Nachweis = { pin: string } | { bild_pin: string[] } | Record<string, never>;

/** Was beim Anlegen und Ändern geht */
export type Profilangaben = Partial<Pick<Profil, "name" | "zeichen" | "farbe" | "rolle" | "geburtsjahr" | "stufe">> & { einstellungen?: Partial<Profileinstellungen> };

const WEG = "/api/familie";
const profilweg = (id: string) => `${WEG}/profile/${encodeURIComponent(id)}`;

export const ladeFamilie = (): Promise<Familie> => get(WEG);
export const ladeStufen = (): Promise<Stufen> => get(`${WEG}/stufen`);
export const ladeIch = (): Promise<Ich> => get(`${WEG}/ich`);
export const waehleProfil = (profil_id: string, nachweis: Nachweis = {}): Promise<Wahl> => post(`${WEG}/wahl`, { profil_id, ...nachweis });
export const verlasseProfil = (eltern_pin?: string): Promise<unknown> => post(`${WEG}/verlassen`, eltern_pin ? { eltern_pin } : {});
export const setzeKatzenname = (name: string): Promise<Katze> => patch(`${WEG}/ich/katze`, { name });
export const meldeLesezeit = (sekunden: number, vorlesen: boolean): Promise<Lesezeitstand> => post(`${WEG}/lesezeit`, { sekunden, vorlesen });

export const legeProfilAn = (angaben: Profilangaben): Promise<Profil> => post(`${WEG}/profile`, angaben);
export const aendereProfil = (id: string, angaben: Profilangaben): Promise<Profil> => patch(profilweg(id), angaben);
export const setzePin = (id: string, wert: { pin: string } | { bild_pin: string[] } | { entfernen: true }): Promise<Profil> => put(`${profilweg(id)}/pin`, wert);
export const profilfolgen = (id: string): Promise<Profilfolgen> => get(`${profilweg(id)}/loeschfolgen`);
export const loescheProfil = (id: string): Promise<unknown> => del(profilweg(id));

export const ladeFreigaben = (id: string): Promise<Freigaben> => get(`${profilweg(id)}/freigaben`);
export const gibFrei = (id: string, art: Freigabeart, ziel_ids: number[]): Promise<unknown> => post(`${profilweg(id)}/freigaben`, { art, ziel_ids });
export const nimmFreigabe = (id: string, art: Freigabeart, ziel_ids: number[]): Promise<unknown> => del(`${profilweg(id)}/freigaben`, { art, ziel_ids });
export const ladeEinblick = (id: string): Promise<Einblick> => get(`${profilweg(id)}/einblick`);

export const bindeGeraet = (profil_id: string, eltern_pin: string): Promise<unknown> => post(`${WEG}/geraet`, { profil_id, eltern_pin });
export const loeseGeraet = (eltern_pin: string): Promise<unknown> => del(`${WEG}/geraet`, { eltern_pin });
