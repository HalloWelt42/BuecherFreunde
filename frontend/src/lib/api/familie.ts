// Familie mit Profilen (BF-78, docs/neubau/FAMILIE.md): Profile, Wahl beim Start, Rechte, Freigaben, Lesezeit, Einblick,
// Katze. Was ein Profil sieht und darf, entscheidet der Server; die Oberfläche zeigt nur, was er erlaubt.
import { del, get, patch, post, put } from "./client";
import type { Buch } from "../typen";

export type Rolle = "verwaltung" | "erwachsen" | "kind";
export type Stufe = "vorlesen" | "erstes_lesen" | "lesen_lernen" | "schule" | "jugend";

/** Was ein Profil darf, aus Rolle und Stufe (stufen.json am Server, dort mit Beschreibung) */
export type Faehigkeit =
  | "lesen" | "vorlesen" | "lesezeichen" | "suche" | "favoriten" | "sammeln" | "markierungen" | "notizen" | "etiketten" | "privat"
  | "ausfuehren" | "nachschlagen" | "katalog" | "hinzufuegen" | "bearbeiten" | "freigeben" | "ki" | "loeschen" | "einstellungen" | "profile"
  /** Lücken in Sammlungen (BF-75): nur Erwachsene */
  | "luecken";

/** Schrift des Kindes, ausgehend von der Größe seiner Stufe */
export type Schriftgroesse = "klein" | "mittel" | "gross";

/** Gestaltung des Kinderbereichs (BF-88): klein verspielt mit großen Tasten, groß ruhig im Stil der App */
export type Gestaltung = "klein" | "gross";
/** Die Uhr im Kopf der Gestaltung groß */
export type Kopfuhr = "zeiger" | "zahl";
/** Leseschrift: normal (serifenlos mit normalen Abständen) oder die Kinderschrift der Stufe */
export type Leseschrift = "normal" | "kinderschrift";

export interface Lesehilfen {
  /** Vorlesen mit Mitlesen: das gelesene Wort leuchtet */
  mitlesen: boolean;
  /** Tempo des Vorlesens, 1 ist normal */
  tempo: number;
  /** Farbige Silben; das Kind schaltet sie selbst an und aus */
  silben: boolean;
  lesezeile: boolean;
  schrift: Schriftgroesse;
  /** Vorgabe der Eltern; in der Gestaltung groß schaltet das Kind beim Lesen selbst um */
  schrift_wahl: Leseschrift;
  /** Hinweise werden gesprochen: Lesezeit, Ruhezeit, Bild-PIN und alles, was sonst nur dasteht */
  hinweise_sprechen: boolean;
  /** Eine gedrückte Taste sagt, was sie tut */
  tasten_ansagen: boolean;
  /** Stimme für Vorlesen und Ansagen: eine der Vertonung ("katalog:<name>" oder die Kennung einer Klonstimme), "geraet" oder leer:
   *  die Stimme der Familie */
  stimme?: string;
}

/** Ein Wert für eine Einstellung der Vertonung (Tempo, Sprache und mehr, nach ihrer Beschreibung) */
export type Sprechwert = boolean | number | string;

/** Vorlesen je Profil (BF-14), gespeichert: die Stimme im Leser (nur Erwachsene) und die Werte der Vertonung */
export interface Vorlesewahl {
  stimme: string | null;
  werte: Record<string, Sprechwert>;
}

/** Womit das aktive Profil vorgelesen bekommt */
export interface Vorlesestand {
  /** Wie die Vertonung sie schreibt, "geraet" oder "geraet:<Stimme des Browsers>"; leer: die Stimme ab Werk der Vertonung */
  stimme: string;
  werte: Record<string, Sprechwert>;
  /** Erwachsene wählen im Leser selbst, für Kinder die Eltern */
  eigene_wahl: boolean;
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
  /** Im Vorlesealter wählt das Kind den Namen aus vorgelesenen Vorschlägen, sonst tippt es ihn */
  name_eingabe?: "vorschlaege" | "tippen";
}

export interface Profileinstellungen {
  lesehilfen: Lesehilfen;
  lesezeit: Lesezeitregel;
  katze: Katze;
  /** null: kein Kinderbereich, die Oberfläche der App (Jugend) */
  gestaltung: Gestaltung | null;
  uhr: Kopfuhr;
  /** Werte der Vertonung für Vorlesen; die Stimme steht in den Lesehilfen */
  vorlesen?: Vorlesewahl;
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
  /** Nur für die, die das Profil ändern dürfen, und für das Profil selbst; sonst null */
  geburtsjahr?: number | null;
  /** Was wirkt (eigene Wahl vor den Vorgaben der Stufe und des Alters); nur bei Kindern */
  einstellungen?: Partial<Profileinstellungen> | null;
}

/** Ein Gerät, das fest auf ein Kind gestellt ist */
export interface Geraetestand {
  /** Das Gerät öffnet nur dieses Profil; leer auch, solange die Wahl nach der PIN der Eltern offen ist */
  gebunden_an: string | null;
  /** Worauf es fest gestellt ist, auch während es offen ist */
  fest_auf: string | null;
  /** Nach der PIN der Eltern darf hier eine Weile jemand anders wählen */
  offen: boolean;
}

/** GET /api/familie */
export interface Familie {
  profile: Profil[];
  /** Es gibt mehr als ein Profil oder eine PIN: ohne Wahl geht es nicht */
  braucht_wahl: boolean;
  /** Das Profil des mitgeschickten Schlüssels, wenn er gilt */
  aktiv: string | null;
  geraet: Geraetestand;
  /** Vorlesestimme der Familie: spricht "Wer liest?" und die Namen, Vorgabe für jedes Kind ohne eigene Wahl; leer: keine */
  stimme: string;
}

export interface Lesezeitstand {
  /** Es gilt eine Grenze oder eine Ruhezeit */
  an: boolean;
  heute_s: number;
  /** null: ohne Grenze */
  grenze_s: number | null;
  rest_s: number | null;
  ruht: boolean;
  /** Bis wann die Ruhezeit gilt, "07:00" */
  ruhe_bis: string | null;
  /** Ab so viel Lesezeit heute kommt der sanfte Hinweis */
  hinweis_ab_s: number | null;
}

/** Darstellung des Kinderbereichs nach Stufe und Schriftwahl (Kinder; Erwachsene leer). Der Kinderbereich liest sie selbst. */
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
  /** Kinder: was wirkt; Erwachsene: null */
  lesehilfen: Lesehilfen | null;
  lesezeit: Lesezeitstand;
  katze: Katze;
  /** Was die Eltern sehen, für das Kind sichtbar; leer bei Erwachsenen */
  einblick: Einblickart[];
  /** Kinderbereich klein oder groß; null: die Oberfläche der App (Jugend, Erwachsene) */
  gestaltung: Gestaltung | null;
  /** Uhr im Kopf der Gestaltung groß; null bei Erwachsenen */
  uhr: Kopfuhr | null;
  vorlesen: Vorlesestand;
}

/** Was die Eltern im Einblick sehen */
export type Einblickart = "titel" | "lesezeit" | "fortschritt" | "grober_fortschritt" | "zuletzt" | "geteiltes";

/** Eine Stufe aus stufen.json */
export interface Stufenangabe {
  schluessel: Stufe;
  name: string;
  /** Für Menschen, etwa "Klasse 1 und 2" */
  alter?: string;
  /** Alter in Jahren, für den Vorschlag aus dem Geburtsjahr */
  alter_von: number;
  /** null: nach oben offen */
  alter_bis: number | null;
  faehigkeiten: Faehigkeit[];
  einblick: Einblickart[];
  /** Lesehilfen der Stufe, Lesezeit für das Alter, ab dem sie gilt, Katze */
  vorgaben?: Partial<Profileinstellungen>;
}

/** Vorgabe der Lesezeit am Tag nach Alter; an false: ohne Grenze */
export interface Lesezeitvorgabe {
  alter_von: number;
  alter_bis: number | null;
  minuten: number;
  an: boolean;
}

/** Wie sich ein Profil ausweist: PIN aus so vielen Ziffern, Bild-PIN aus so vielen dieser Bilder in ihrer Folge */
export interface Zugang {
  pin_stellen_von: number;
  pin_stellen_bis: number;
  bild_pin_anzahl: number;
  bilder: string[];
}

/** GET /api/familie/stufen */
export interface Stufen {
  stufen: Stufenangabe[];
  lesezeit: Lesezeitvorgabe[];
  /** Fähigkeit -> was sie erlaubt */
  faehigkeiten?: Partial<Record<Faehigkeit, string>>;
  zugang?: Zugang;
  katze_vorschlaege?: string[];
  katze_nennung?: string;
}

/** Antwort auf die Wahl: der Schlüssel für X-Profil und das Profil samt Rechten */
export interface Wahl {
  schluessel: string;
  profil: Ich;
}

/** Was mit einem Profil verloren geht; `stand` geht mit dem Löschen zurück, ändert sich seither etwas, gilt er nicht mehr */
export interface Profilfolgen {
  profil?: Profil;
  notizen: number;
  markierungen: number;
  etiketten: number;
  /** Bücher mit Lesestand, Favorit, Sternen oder Lesesofa */
  lesestaende: number;
  vorlesestellen: number;
  /** Lesestände in Übersetzungen */
  fassungen_gelesen: number;
  freigaben: number;
  /** Kein Buch wird gelöscht; sie sind danach für alle sichtbar */
  private_buecher: number;
  lesezeit_tage: number;
  /** Fest auf dieses Profil gestellte Geräte, sie werden gelöst */
  geraete: number;
  stand: string;
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
  /** Anteil 0 bis 1, ab Schule nur grob; null: sieht man nicht */
  fortschritt: number | null;
  /** Nur mit genauem Fortschritt */
  seite?: number | null;
  seiten?: number | null;
  zuletzt?: string | null;
}

export interface Einblick {
  sichtbar: Einblickart[];
  /** Je Kind und Tag, nicht je Buch; null: sieht man nicht */
  lesezeit_heute_s?: number | null;
  eintraege: Einblickeintrag[];
}

/** Die Ansagen spricht das Gerät selbst; gedacht für Installationen ohne Vertonung */
export const GERAETESTIMME = "geraet";

/** Der Auftrag "Ansagen erstellen" für eine Stimme: wie weit, seit wann, warum nicht */
export interface Ansagenstand {
  was: string;
  stimme: string;
  stand: "wartet" | "laeuft" | "fertig" | "fehler";
  gesamt: number;
  fertig: number;
  /** Warum es nicht weitergeht, etwa ohne Vertonung */
  grund: string;
  begonnen: string | null;
  geaendert: string | null;
  fertig_am: string | null;
}

/** Ein fester Satz: sein Text und die Adresse seines Tons; ohne Adresse spricht ihn die Stimme des Geräts */
export interface Ansageeintrag {
  text: string;
  url: string | null;
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
/** Die eigene Stimme im Leser (Erwachsene); leer: die Stimme ab Werk der Vertonung */
export const setzeVorlesestimme = (stimme: string): Promise<Vorlesestand> => patch(`${WEG}/ich/vorlesen`, { stimme });
export const meldeLesezeit = (sekunden: number, vorlesen: boolean): Promise<Lesezeitstand> => post(`${WEG}/lesezeit`, { sekunden, vorlesen });

export const legeProfilAn = (angaben: Profilangaben): Promise<Profil> => post(`${WEG}/profile`, angaben);
export const aendereProfil = (id: string, angaben: Profilangaben): Promise<Profil> => patch(profilweg(id), angaben);
export const setzePin = (id: string, wert: { pin: string } | { bild_pin: string[] } | { entfernen: true }): Promise<Profil> => put(`${profilweg(id)}/pin`, wert);
export const profilfolgen = (id: string): Promise<Profilfolgen> => get(`${profilweg(id)}/loeschfolgen`);
/** Nur mit dem `stand` der Löschfolgen; 409, wenn sich seither etwas geändert hat */
export const loescheProfil = (id: string, stand: string): Promise<unknown> => del(`${profilweg(id)}?${new URLSearchParams({ stand })}`);
/** Die PIN der Verwaltung fällt weg, wenn sich das Konto des Geräts erneut anmeldet */
export const vergissPin = (id: string, kennung: string, passwort: string): Promise<Familie> => post(`${profilweg(id)}/pin/vergessen`, { kennung, passwort });

export const ladeFreigaben = (id: string): Promise<Freigaben> => get(`${profilweg(id)}/freigaben`);
export const gibFrei = (id: string, art: Freigabeart, ziel_ids: number[]): Promise<unknown> => post(`${profilweg(id)}/freigaben`, { art, ziel_ids });
export const nimmFreigabe = (id: string, art: Freigabeart, ziel_ids: number[]): Promise<unknown> => del(`${profilweg(id)}/freigaben`, { art, ziel_ids });
export const ladeEinblick = (id: string): Promise<Einblick> => get(`${profilweg(id)}/einblick`);

/** Der Probesatz in dieser Stimme; mit der Stimme des Geräts nur der Text */
export const ansageProbe = (stimme: string): Promise<Ansageeintrag> => post(`${WEG}/ansagen/probe`, { stimme });
/** Der Auftrag "Ansagen erstellen" dieser Stimme; leer, solange es keinen gab */
export const ansagenStand = async (stimme: string): Promise<Ansagenstand | null> =>
  (await get<Ansagenstand[]>(`${WEG}/ansagen/stand`, { stimme })).find((s) => s.stimme === stimme) ?? null;
/** Die Stimme der Familie (Fähigkeit profile) */
export const setzeFamilienstimme = (stimme: string): Promise<{ stimme: string }> => put(`${WEG}/stimme`, { stimme });

export const bindeGeraet = (profil_id: string, eltern_pin: string): Promise<unknown> => post(`${WEG}/geraet`, { profil_id, eltern_pin });
/** Mit der PIN der Eltern; als Verwaltung ohne sie */
export const loeseGeraet = (eltern_pin?: string): Promise<unknown> => del(`${WEG}/geraet`, eltern_pin ? { eltern_pin } : {});
/** Das Kind teilt ein Buch mit den Eltern (ab Jugend sehen sie nur Geteiltes) */
export const teileBuch = (buch: number, geteilt: boolean): Promise<{ geteilt: boolean }> => put(`/api/books/${buch}/geteilt`, { geteilt });
