// Die Daten der Schnittstelle, so wie der Server sie liefert

export interface RegalKurz {
  id: number;
  name: string;
  slug?: string;
  quelle?: string;
  /** Nur an Kategorien des Katalogs (BF-69): Zeichen, Farbe (die des Bereichs, wenn die eigene leer ist), Name des Bereichs */
  zeichen?: string;
  farbe?: string;
  bereich?: string;
  art?: Kategorieart;
}

/** Was eine Zeile in categories ist (BF-69): Ebene des Katalogs oder Regal wie bisher */
export type Kategorieart = "bereich" | "kategorie" | "regal";

/** Kategorie am Server, in der Oberfläche "Regal" */
export interface Regal extends RegalKurz {
  description: string;
  color: string;
  icon: string;
  sort_order: number;
  spezial: number | boolean;
  buch_anzahl: number;
}

// Katalog (BF-69, docs/neubau/KATALOG.md): Bereiche mit Kategorien darunter, je mit Zeichen und Farbe

/** Regeln einer Kategorie; ein Treffer reicht */
export interface Kategorieregeln {
  sachgruppen: string[];
  schlagworte: string[];
  titelwoerter: string[];
  verlage: string[];
}

export type Regelart = keyof Kategorieregeln;

/** Woher eine Kategorie im Katalog kommt */
export type Herkunft = "standard" | "geteilt" | "neu" | "eigen";

export interface Katalogkategorie {
  /** Fehlt im Entwurf */
  id?: number;
  schluessel: string;
  name: string;
  zeichen: string;
  /** Leer: die Farbe des Bereichs */
  farbe: string;
  ki_beschreibung: string;
  regeln: Kategorieregeln;
  verborgen: boolean;
  /** In einer geladenen Datei auch leer */
  herkunft: Herkunft | "" | null;
  /** Bücher; im Entwurf die Treffer der Regeln, im Standard null */
  anzahl: number | null;
  /** Nur im Standard und in Dateien: Teile, in die eine große Kategorie im Entwurf zerfällt; bleiben, wie sie kamen */
  teile?: unknown[];
}

export interface Katalogbereich {
  id?: number;
  schluessel: string;
  name: string;
  zeichen: string;
  farbe: string;
  beschreibung: string;
  /** Für welche Arten des Werks der Bereich gilt, mindestens eine: "" für Buch, sonst etwa "dokument", "heft" */
  arten: string[];
  verborgen: boolean;
  /** Nur im Entwurf */
  herkunft?: Herkunft | null;
  anzahl: number | null;
  kategorien: Katalogkategorie[];
}

/** Ein Regal außerhalb des Katalogs (GET /api/katalog) */
export interface Katalogregal {
  id: number;
  name: string;
  zeichen: string;
  farbe: string;
  anzahl: number;
  spezial: boolean;
}

/** GET /api/katalog: der gültige Katalog */
export interface Katalog {
  bereiche: Katalogbereich[];
  regale: Katalogregal[];
  /** Bücher ohne Kategorie des Katalogs */
  ohne_kategorie: number;
  hat_katalog: boolean;
}

/** Ein Katalog, der noch nicht gilt: aus dem Standard, an den Bestand angepasst, geladen oder leer */
export interface Katalogentwurf {
  fassung?: number;
  bereiche: Katalogbereich[];
}

/** Wie ein Entwurf entsteht */
export type Katalogweg = "standard" | "bestand" | "leer";

/** Stand eines Laufs: Einordnen oder Entwurf aus dem Bestand */
export interface Laufstand {
  laeuft: boolean;
  pause: boolean;
  /** leer: es gab noch keinen Lauf */
  stand?: "laeuft" | "pause" | "fertig" | "fehler" | "";
  stapel: number;
  stapel_gesamt: number;
  stapel_groesse: number;
  /** Vorschläge der Regeln und der KI, Bücher ohne Vorschlag */
  regeln: number;
  ki: number;
  ohne_vorschlag: number;
  /** Was der Lauf gerade tut */
  schritt: string;
  /** Warum er pausiert oder endete; leer sonst */
  grund: string;
}

/** GET /api/katalog/entwurf */
export interface Entwurfsstand {
  entwurf: Katalogentwurf | null;
  lauf: Laufstand | null;
}

/** Was vor dem Entfernen eines Bereichs oder einer Kategorie verloren geht */
export interface Katalogfolgen {
  name: string;
  /** Bücher verlieren die Zuordnung, sie selbst bleiben */
  buecher: number;
  /** offene Vorschläge, die wegfallen */
  vorschlaege: number;
  /** bei einem Bereich: seine Kategorien */
  kategorien: number;
  /** die ersten betroffenen Bücher */
  titel: string[];
}

/** Was vor dem Entfernen eines alten Regals verloren geht */
export interface Altfolgen {
  id: number;
  name: string;
  buecher: number;
  /** davon in keiner Kategorie des Katalogs */
  ohne_kategorie: number;
  titel: string[];
}

/** GET /api/katalog/kategorien/{id}/treffer */
export interface Kategorietreffer {
  regeln: { art: Regelart; werte: string[]; treffer: number }[];
  /** Bücher, die mindestens eine Regel trifft */
  zusammen: number;
  ki_vorschlaege: number;
}

/** Ein Regal aus Importen und wohin es im Katalog gehört (GET /api/katalog/alt) */
export interface AltesRegal {
  id: number;
  name: string;
  anzahl: number;
  vorschlag: { art: "kategorie" | "schlagwort"; kategorie_id: number | null; grund: string };
}

/** Wohin alte Regale gehen: in eine Kategorie oder als Schlagwort ans Buch */
export type Altziel = { kategorie_id: number } | { schlagwort: true };

export type Vorschlagsquelle = "regel" | "ki" | "beide";

/** Ein Buch in einer Kategorie, gefunden von Regel oder KI */
export interface Katalogvorschlag {
  id: number;
  buch: Buch;
  kategorie_id: number;
  quelle: Vorschlagsquelle;
  /** Kurze Sätze: die Regel oder der Satz der KI */
  gruende: string[];
  /** 0 bis 100 */
  sicherheit: number;
  /** Sicher genug, um vorab angehakt zu sein */
  vorab: boolean;
  /** Die übrigen offenen Vorschläge für dasselbe Buch; mit id lassen sie sich gleich mit annehmen */
  auch: { id: number; kategorie_id: number; name: string; sicherheit: number }[];
}

/** GET/PUT /api/katalog/einstellungen */
export interface Katalogeinstellungen {
  /** Titel je Stapel eines Laufs */
  stapel: number;
  /** Bücher je Anfrage an die KI */
  ki_je_anfrage: number;
  /** So sichere Vorschläge stehen vorab angehakt */
  sicher_ab: number;
  /** Über so vielen Treffern zerfällt eine Kategorie im Entwurf in ihre Teile */
  teilen_ab: number;
}

export interface Vorschlagsseite {
  gesamt: number;
  vorschlaege: Katalogvorschlag[];
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
  /** Zuletzt gelesen, auch wenn es nicht fertig ist */
  last_read_at: string | null;
  /** Fertig gelesen (Lesestand am Ende oder markiert, BF-78); leer: noch nicht */
  fertig_am?: string | null;
  categories: RegalKurz[];
  sammlung: SammlungKurz | null;
  created_at: string;
  updated_at: string;
  /** Nur das aktive Profil sieht das Buch (BF-78) */
  privat?: boolean;
  /** Altersangabe aus den Quellen, nur Hilfe beim Freigeben (BF-78); null: keine */
  alter_von?: number | null;
  alter_bis?: number | null;
  /** Woher die Altersangabe kommt, etwa der Name einer Quelle oder "eigen" */
  alter_quelle?: string;
  /** So viele Dateien Begleitmaterial (BF-81) */
  material?: number;
  /** Die Prüfung der Originale fand die Datei nicht (BF-82); null: das Original ist da oder ungeprüft */
  original?: { text: string; geprueft_am: string | null } | null;
  /** Die Texterkennung hat es als Scan eingestuft: der Leser zeigt nur das Original, keine Textansicht (BF-123) */
  scan?: boolean;
}

/** Eine Datei des Buchs (BF-80): das Original oder ein weiteres Format */
export interface Buchdatei {
  id: string;
  format: string;
  name: string;
  groesse: number;
  /** Das Original, aus dem Text, Umschlag und Angaben stammen */
  haupt: boolean;
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
  /** Weitere Formate (BF-80) und Begleitmaterial (BF-81), gehen mit dem Buch */
  formate?: { pfad: string; groesse: number; papierkorb: boolean }[];
  material?: { pfad: string; groesse: number; papierkorb: boolean }[];
}

export interface BuchEinzeln extends Buch {
  language: string;
  description: string;
  file_name: string;
  authors: AutorKurz[];
  /** Das Original zuerst, dann weitere Formate (BF-80) */
  dateien?: Buchdatei[];
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
  /** Lücken aus den eigenen Bandnummern, etwa "vorhanden 1 bis 5 und 8, es fehlen 6 und 7" (BF-75); leer ohne */
  luecken?: string;
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
  /** Werke der Art Buch und alles, was kein Buch ist (BF-77) */
  buecher: number;
  besonderes: number;
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

/** Ein Treffer im Begleitmaterial (BF-81): er nennt das Buch und die Datei, bei einem PDF die Seite */
export interface Materialtreffer {
  material_id: string;
  buch_id: number;
  titel: string;
  autor: string;
  name: string;
  seite: number | null;
  auszug: string;
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
  stand: Guete | "aus";              // aus: noch nichts bekannt (etwa ein Lexikon im Netz, das noch nie gefragt wurde)
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

/** Stand des Laufs, der die Art aller Werke bestimmt (GET /api/einordnung/stand, BF-59, BF-77) */
export interface Einordnungsstand {
  /** Eingeschaltet in der Einrichtung */
  an: boolean;
  /** An und eine Leitstelle eingetragen */
  bereit: boolean;
  laeuft: boolean;
  /** Die Leitstelle hat abgelehnt; weiter mit POST /api/einordnung/fortsetzen */
  angehalten: boolean;
  grund: string;
  /** Alle Werke, davon nach Regel, durch die KI und noch offen */
  gesamt: number;
  nach_regel: number;
  durch_ki: number;
  offen: number;
}
