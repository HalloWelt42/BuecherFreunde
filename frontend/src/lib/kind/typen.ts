// Was der Kinderbereich (BF-78, docs/neubau/FAMILIE.md) vom Server bekommt und was er selbst daraus macht. Die Rohform kommt aus
// GET /api/familie/ich; lib/kind/ich.ts macht daraus ein vollständiges Ich, damit keine Ansicht mit fehlenden Feldern rechnet.

export type Stufe = "vorlesen" | "erstes_lesen" | "lesen_lernen" | "schule" | "jugend";

export const STUFEN: Stufe[] = ["vorlesen", "erstes_lesen", "lesen_lernen", "schule", "jugend"];

/** Was ein Kind darf; die Stufe (stufen.json des Servers) bestimmt es, die Oberfläche zeigt nur das */
export type Faehigkeit = "lesen" | "vorlesen" | "lesezeichen" | "suche" | "favoriten" | "gelesen" | "markierungen" | "notizen";

export interface Kinderprofil {
  id: string;
  name: string;
  /** Symbol aus Font Awesome, ohne "fa-" */
  zeichen: string;
  farbe: string;
  rolle: "verwaltung" | "erwachsen" | "kind";
  stufe: Stufe | null;
}

/** Wie das Kind liest: Schrift, Größe, Zeilen, Abstände, Tasten und die Lesehilfen, die die Eltern erlauben */
export interface Kinderdarstellung {
  /** CSS-Schriftfamilie des Lesetexts */
  schrift: string;
  /** Lesetext in Pixeln bei normaler Schriftstufe der App */
  groesse: number;
  fett: boolean;
  /** Zeilenabstand als Vielfaches der Schriftgröße */
  zeilenabstand: number;
  /** Höchstens so viele Wörter je Zeile; 0: nur nach Breite */
  woerter_je_zeile: number;
  /** Höchstens so viele Zeichen je Zeile */
  zeichen_je_zeile: number;
  /** Abstände als Anteil der Schriftgröße */
  abstand_absatz: number;
  abstand_buchstabe: number;
  abstand_wort: number;
  /** Kantenlänge einer Taste in Millimetern */
  tippflaeche_mm: number;
  /** Lesehilfen: an heißt, das Kind hat sie und schaltet sie selbst an und aus */
  silben: boolean;
  lesezeile: boolean;
  /** Beim Vorlesen das gelesene Wort zeigen */
  mitlesen: boolean;
  /** Tempo des Vorlesens, 1 ist normal */
  tempo: number;
  /** Ein Buch liest sich beim Öffnen von selbst vor */
  vorlesen_von_selbst: boolean;
}

/** Lesezeit von heute, wie der Server sie rechnet (GET /api/familie/ich, Antwort von POST /api/familie/lesezeit) */
export interface Lesezeitstand {
  heute_s: number;
  /** Was heute noch bleibt, mit einer nahen Ruhezeit verrechnet; null: ohne Grenze */
  rest_s: number | null;
  /** Gerade ist Ruhezeit */
  ruht: boolean;
  /** Ab wann wieder gelesen werden darf ("07:00" oder ein Zeitpunkt), wenn der Server es weiß */
  ruhe_bis: string | null;
  /** Ab wann Ruhezeit ist ("19:30" oder ein Zeitpunkt); null: ohne oder unbekannt */
  ruhe_ab: string | null;
  /** Ab so viel Rest kommt der sanfte Hinweis; null: kein Hinweis in dieser Stufe */
  hinweis_ab_s: number | null;
}

export interface Katzenstand {
  an: boolean;
  /** Leer: das Kind hat ihr noch keinen Namen gegeben */
  name: string;
  schnurren: boolean;
}

/** Wach im Regal, schläft beim Lesen, ruht auf dem Ruheschirm */
export type Katzenzustand = "wach" | "schlaeft" | "ruht";

export interface Ich {
  profil: Kinderprofil;
  faehigkeiten: ReadonlySet<Faehigkeit>;
  darstellung: Kinderdarstellung;
  lesezeit: Lesezeitstand;
  katze: Katzenstand;
}

/** Ein Wort im Text einer Einheit, mit seiner Lage darin (Zeichen von bis, ausschließlich) */
export interface Wort {
  text: string;
  von: number;
  bis: number;
}

export interface Bild {
  adresse: string;
  /** Breite durch Höhe, wenn bekannt */
  verhaeltnis: number | null;
  /** Beschreibung aus dem Buch */
  text: string;
}

/** Ein Baustein einer Einheit, wie der Kinderleser ihn zeigt */
export type Kinderblock =
  | { art: "titel" | "absatz"; von: number; woerter: Wort[] }
  | { art: "bild"; von: number; bild: Bild };

/** Eine Einheit des Buchs (Seite eines PDF, Abschnitt eines EPUB, Stück eines Textes) mit ihrem ganzen Text */
export interface Einheit {
  nr: number;
  /** Text wie beim Vorlesen: Absätze durch eine Leerzeile getrennt; alle Lagen beziehen sich darauf */
  text: string;
  bloecke: Kinderblock[];
}

/** Stelle im Buch: Einheit und Zeichen darin */
export interface Kinderstelle {
  einheit: number;
  zeichen: number;
}
