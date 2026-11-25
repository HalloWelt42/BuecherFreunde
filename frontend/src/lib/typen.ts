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

export interface BuchEinzeln extends Buch {
  language: string;
  description: string;
  file_name: string;
  authors: AutorKurz[];
}

export interface BuchListe {
  buecher: Buch[];
  gesamt: number;
  seite: number;
  pro_seite: number;
  seiten_gesamt: number;
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

export interface Treffer {
  book_id: number;
  titel: string;
  autor: string;
  snippet: string;
  relevanz: number;
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
