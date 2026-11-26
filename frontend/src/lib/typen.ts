// Die Daten der Schnittstelle, so wie der Server sie liefert

export interface RegalKurz {
  id: number;
  name: string;
  slug?: string;
  quelle?: string;
}

/** Kategorie am Server, in der Oberfläche "Regal" */
export interface Regal extends RegalKurz {
  description: string;
  color: string;
  icon: string;
  sort_order: number;
  spezial: number | boolean;
  buch_anzahl: number;
}

export interface SammlungKurz {
  id: number;
  name: string;
  color?: string;
}

export interface Sammlung extends SammlungKurz {
  description: string;
  color: string;
  buch_anzahl: number;
}

export interface AutorKurz {
  id: number;
  name: string;
}

/** Welches Blatt ein Buch zeigt (BF-59): das gestaltete oder die Titelseite aus der Datei */
export type Umschlagart = "gestaltet" | "titelseite";

/** Art eines Eintrags (GET /api/collections/typen); leer heißt Buch */
export interface Art {
  id: string;
  name: string;
  beschreibung?: string;
}

/** Gattung eines Buchs (GET /api/collections/gattungen) */
export interface Gattung {
  id: string;
  name: string;
}

export interface Buch {
  id: number;
  hash: string;
  title: string;
  author: string;
  publisher: string;
  file_format: string;
  file_size: number;
  cover_path: string;
  cover_stand?: number;
  page_count: number;
  year: number | null;
  isbn: string;
  typ: string;
  /** Kennung der Gattung, leer ohne */
  gattung: string;
  /** Was der Umschlag zeigt, vom Server bestimmt aus Titelseite und Wahl */
  umschlag: Umschlagart;
  /** Die Titelseite ist fast weiß; dann gibt es die Wahl */
  umschlag_schlicht: boolean;
  /** Eigene Wahl; leer folgt dem Server */
  umschlag_wahl: "" | Umschlagart;
  sammlung_id: number | null;
  band_nummer: string;
  is_favorite: boolean;
  is_to_read: boolean;
  rating: number;
  reading_position: string;
  last_read_at: string | null;
  categories: RegalKurz[];
  sammlung: SammlungKurz | null;
  created_at: string;
  updated_at: string;
}

/** Was mit einem Buch verloren geht (BF-60, GET /api/books/{id}/loeschfolgen) */
export interface Loeschfolgen {
  titel: string;
  autor: string;
  notizen: number;
  markierungen: number;
  etiketten: number;
  lesestand: boolean;
  vorlesestelle: boolean;
  regale: number;
  /** papierkorb: kommt in den Papierkorb der Kellerwolke; sonst liegt sie nur hier und ist danach fort */
  datei: { pfad: string; groesse: number; papierkorb: boolean } | null;
  /** Abschnitte der Suche nach Bedeutung; null ohne Anschluss */
  abschnitte: number | null;
}

export interface BuchEinzeln extends Buch {
  language: string;
  description: string;
  file_name: string;
  authors: AutorKurz[];
}

/** Eine große Sammlung als ein Eintrag der Bibliothek (BF-66) */
export interface Sammlungseintrag {
  id: number;
  name: string;
  /** Bücher der Sammlung */
  anzahl: number;
  autor: string;
  /** Bis drei Bücher für den Stapel, das vorderste zuerst */
  umschlaege: Buch[];
}

/** Ein Eintrag der Bibliothek: ein Buch oder eine zusammengefasste Sammlung */
export type Eintrag = { art: "buch"; buch: Buch } | { art: "sammlung"; sammlung: Sammlungseintrag };

export interface BuchListe {
  /** Mit zusammenfassen nur die einzeln gezeigten Bücher */
  buecher: Buch[];
  /** Bücher, auch die in zusammengefassten Sammlungen */
  gesamt: number;
  seite: number;
  pro_seite: number;
  seiten_gesamt: number;
  /** Nur mit Schnellfilter: wie viele es ohne ihn wären */
  gesamt_ohne_suche?: number | null;
  /** Nur mit zusammenfassen (BF-66): Bücher und Sammlungen in Anzeigereihenfolge */
  eintraege?: Eintrag[];
  /** Nur mit zusammenfassen: Einträge insgesamt, danach wird geblättert */
  gesamt_eintraege?: number;
  /** Nur mit zusammenfassen: Bücher in den zusammengefassten Sammlungen */
  in_sammlungen?: number;
  /** Nur mit zusammenfassen: wie viele Sammlungen als ein Eintrag stehen */
  sammlungen_zusammengefasst?: number;
}

/** GET/PUT /api/collections/einstellungen */
export interface Sammlungseinstellungen {
  /** Ab so vielen Büchern steht eine Sammlung als ein Eintrag in der Liste */
  als_eintrag_ab: number;
}

/** Ein Buch eines Vorschlags mit der Bandnummer, die der Fund ihm gibt */
export interface Vorschlagsbuch extends Buch {
  /** Leer ohne Nummer */
  band: string;
}

/** Eine gefundene Reihe, die noch keine Sammlung ist (GET /api/collections/vorschlaege) */
export interface Sammlungsvorschlag {
  id: number;
  name: string;
  autor: string;
  anzahl: number;
  /** Fundwege der Regeln, etwa "Reihenname mit Nummer" */
  wege: string[];
  /** Satz der lokalen KI, oder warum sie nicht geprüft hat */
  ki: string;
  /** Hat die KI den Fund geprüft? Sonst steht in ki der Grund */
  ki_geprueft: boolean;
  /** Die KI hält es für keine Reihe; der Vorschlag bleibt, du entscheidest (steht am Ende der Liste) */
  ki_zweifel: boolean;
  buecher: Vorschlagsbuch[];
}

/** Stand des Suchlaufs (GET /api/collections/vorschlaege/stand, auch die Antwort auf suchen) */
export interface Vorschlagsstand {
  laeuft: boolean;
  /** Was der Lauf gerade tut */
  schritt: string;
  /** Offene Vorschläge; während des Laufs die bisher gefundenen */
  gefunden: number;
  /** Warum die KI nicht geprüft hat oder warum der Lauf endete; leer sonst */
  grund: string;
}

export interface Zahlen {
  buecher_gesamt: number;
  favoriten: number;
  leseliste: number;
  gelesen: number;
  ungelesen: number;
  buecher_mit_isbn: number;
  dokumente: number;
  weiterlesen: number;
  autoren: number;
  mit_labels: number;
  mit_highlights: number;
}

export interface Notiz {
  id: number;
  book_id: number;
  content: string;
  page_reference: string | number | null;
  cfi_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface Markierung {
  id: number;
  book_id: number;
  cfi_range: string;
  color: string;
  text_snippet: string;
  label_name: string;
  label_note: string;
  created_at: string;
}

export interface Etikett {
  id: number;
  book_id: number;
  name: string;
  note: string;
  color: string;
  position?: string;
  position_label?: string;
  created_at: string;
}

/** Was ein Treffer braucht, um sein Deckblatt zu zeigen wie die Bücherliste (BF-59, services/deckblattangaben.py) */
export interface Deckblattangaben {
  typ: string;
  gattung: string;
  umschlag: Umschlagart;
  umschlag_schlicht: boolean;
  umschlag_wahl: "" | Umschlagart;
  cover_path: string;
  file_format: string;
  year: number | null;
}

export interface Treffer {
  book_id: number;
  titel: string;
  autor: string;
  snippet: string;
  relevanz: number;
  deckblatt: Deckblattangaben | null;
}

export interface Bedeutungstreffer {
  buch_id: number;
  titel: string;
  autor: string;
  seite: number | null;
  gedruckt: string | null;
  auszug: string;
  naehe: "sehr nah" | "verwandt";
  wert: number;
  deckblatt: Deckblattangaben | null;
}

export interface BedeutungAntwort {
  verfuegbar: boolean;
  grund: string | null;
  treffer: Bedeutungstreffer[];
}

export type Guete = "gut" | "warn" | "schlecht";

export interface Verbindung {
  kennung: string;
  name: string;
  stand: Guete;
  text: string;
}

export interface Ort {
  kennung: string;
  name: string;
  pfad: string;
  belegt: number | null;
  frei: number | null;
  stand: Guete;
}

export interface Wolkenablage {
  pfad: string;
  groesse: number;
  sha256: string;
  in_der_wolke?: boolean;
}

export interface Ablage {
  wolke: Wolkenablage | null;
  volltext: { seiten: number; zeichen: number } | null;
  wissen: { stand: Guete; text: string; abschnitte?: number | null } | null;
}
