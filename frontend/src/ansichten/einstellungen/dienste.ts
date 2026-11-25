// Quellen und Dienste: was sie liefern und welche Felder daraus werden
import { kiStatus } from "../../lib/api/ai";
import { gutenbergStatus, healthCheck, ladeConfig, quellenStatus, type Erreichbarkeit } from "../../lib/api/config";
import type { Guete } from "../../lib/typen";

export type Zuordnung = [quelle: string, ziel: string];

export interface Dienst {
  kennung: string;
  name: string;
  symbol: string;
  stand: Guete | "aus";
  wort: string;
  text: string;
  adresse: string;
  beschreibung: string;
  felder: Zuordnung[];
  autoren?: Zuordnung[];
  konfidenz?: string;
  roh?: string[];
}

type Beschreibung = Pick<Dienst, "kennung" | "name" | "symbol" | "adresse" | "beschreibung" | "felder" | "autoren" | "konfidenz" | "roh">;

const beschreibungen: Record<string, Beschreibung> = {
  server: { kennung: "server", name: "Server", symbol: "server", adresse: "", beschreibung: "Verwaltet Bücher, Regale, Suche, Aufnahme und Einstellungen und liefert alles über eine Schnittstelle aus.", felder: [] },
  oberflaeche: { kennung: "oberflaeche", name: "Oberfläche", symbol: "display", adresse: "", beschreibung: "Diese Seite. Spricht nur mit dem Server.", felder: [] },
  verzeichnis1: {
    kennung: "verzeichnis1", name: "Verzeichnis 1", symbol: "book-atlas", adresse: "https://www.googleapis.com/books/v1",
    beschreibung: "Erste Quelle für Angaben: Titel, Autor, Verlag, ISBN, Beschreibung, Umschlag und Kategorien. Ohne eigenen Schlüssel nur wenige Anfragen am Tag.",
    felder: [["volumeInfo.title", "Titel"], ["volumeInfo.authors", "Autor"], ["volumeInfo.publisher", "Verlag"], ["volumeInfo.publishedDate", "Jahr"], ["volumeInfo.pageCount", "Seiten"], ["volumeInfo.industryIdentifiers", "ISBN"], ["volumeInfo.language", "Sprache"], ["volumeInfo.description", "Beschreibung"], ["volumeInfo.categories", "Regale"], ["volumeInfo.imageLinks", "Umschlag"]],
    roh: ["untertitel", "erscheinungsdatum", "identifiers", "lesemodi", "altersfreigabe", "inhaltsversion", "vorschau_link", "info_link", "google_books_link", "durchschnittsbewertung", "anzahl_bewertungen", "abmessungen"],
  },
  verzeichnis2: {
    kennung: "verzeichnis2", name: "Verzeichnis 2, Open Library", symbol: "book-open", adresse: "https://openlibrary.org/api",
    beschreibung: "Offene Bibliotheksdatenbank mit vielen Angaben, Themen, Auszügen und Verweisen. Höchstens so viele Anfragen je Sekunde, wie eingestellt sind.",
    felder: [["title", "Titel"], ["authors[].name", "Autor"], ["publishers[].name", "Verlag"], ["publish_date", "Jahr"], ["number_of_pages", "Seiten"], ["identifiers", "ISBN"], ["subjects/subject_*", "Regale"], ["cover.large", "Umschlag"]],
    roh: ["identifiers", "excerpts", "links", "subjects", "subject_places", "subject_people", "subject_times"],
  },
  lexikon: {
    kennung: "lexikon", name: "Lexikon, Wikipedia", symbol: "landmark", adresse: "https://www.wikidata.org/w/api.php",
    beschreibung: "Strukturierte Angaben und Beschreibungen. Sucht Bücher über die ISBN und Autoren über den Namen, mit Punkten für jede Übereinstimmung. Liefert Angaben, Lebensläufe und Werklisten.",
    felder: [["labels (de/en)", "Titel"], ["P50 (Autor)", "Autor"], ["P123 (Verlag)", "Verlag"], ["P577 (Erscheinungsdatum)", "Jahr"], ["P1104 (Seitenanzahl)", "Seiten"], ["P212/P957 (ISBN)", "ISBN"], ["P407 (Sprache)", "Sprache"], ["dewiki Auszug", "Beschreibung"], ["P136 (Genre) und P921 (Thema)", "Regale"]],
    autoren: [["P106 (Beruf)", "Konfidenz, 10 Punkte"], ["Gleicher Name", "Konfidenz, 8 Punkte"], ["Eintrag in dewiki", "Konfidenz, 5 Punkte"], ["Zahl der Einträge", "Konfidenz, 1 bis 10 Punkte"], ["P800 (Werke) gegen Bibliothek", "Konfidenz, 15 Punkte"], ["ISBN in Werken", "Konfidenz, 30 Punkte"], ["dewiki Volltext", "Lebenslauf"], ["P18 (Bild)", "Foto in drei Größen"], ["P800 (bekannte Werke)", "Werkliste"], ["P27 (Staatsangehörigkeit)", "Land"], ["P569/P570 (Geburt und Tod)", "Lebensdaten"]],
    konfidenz: "Hoch: ab 15 Punkten oder mit Treffer bei Buch oder ISBN. Mittel: 8 bis 14 Punkte. Niedrig: unter 8 Punkten.",
    roh: ["wikidata_id", "kurzbeschreibung", "isbn13", "isbn10", "autoren", "verlage", "sprachen", "genres", "themen", "typen", "wikipedia_titel", "sitelinks"],
  },
  ki: { kennung: "ki", name: "KI", symbol: "robot", adresse: "", beschreibung: "Liest Titel, Autor und einen Textauszug und schlägt Regale mit Wahrscheinlichkeit vor.", felder: [["Auswertung", "Regale, Vorschläge mit Konfidenz"]] },
  gutenberg: {
    kennung: "gutenberg", name: "Gutenberg", symbol: "landmark-dome", adresse: "https://gutendex.com",
    beschreibung: "Gemeinfreie Bücher: suchen nach Titel, Autor und Sprache, ansehen und als EPUB oder Text übernehmen.",
    felder: [["id", "Nummer"], ["title", "Titel"], ["authors[].name", "Autor"], ["languages[]", "Sprachen"], ["formats (epub/txt)", "Datei"], ["formats (image/jpeg)", "Umschlag"], ["bookshelves[]", "Regale"], ["subjects[]", "Themen"], ["download_count", "Zahl der Downloads"]],
    roh: ["gutenberg_id", "sprachen", "regale", "themen"],
  },
};

/** Eingerichtet heißt: in der Konfiguration an. Verbunden heißt: gerade wirklich geantwortet. */
function standAus(eingerichtet: boolean, pruefung: Erreichbarkeit | null): Pick<Dienst, "stand" | "wort"> {
  if (!eingerichtet) return { stand: "aus", wort: "Aus" };
  if (!pruefung) return { stand: "warn", wort: "Eingerichtet, nicht geprüft" };
  return pruefung.erreichbar ? { stand: "gut", wort: "Verbunden" } : { stand: "schlecht", wort: "Nicht erreichbar" };
}

/** Der Grund "Deaktiviert" steht schon als Wort daneben */
const grund = (e: Erreichbarkeit | null | undefined): string | undefined => (e?.grund && e.grund !== "Deaktiviert" ? e.grund : undefined);

const wert = <T>(e: PromiseSettledResult<T>): T | null => (e.status === "fulfilled" ? e.value : null);

export async function pruefeDienste(): Promise<Dienst[]> {
  const [gesund, konfiguration, quellen, ki, gutenberg] = await Promise.allSettled([healthCheck(), ladeConfig(), quellenStatus(), kiStatus(), gutenbergStatus()]);
  const k = wert(konfiguration);
  const q = wert(quellen);
  const g = wert(gesund) as { version?: string } | null;
  const b = beschreibungen;
  const dienste: Dienst[] = [
    { ...b.server, adresse: `${location.origin}/api`, ...(g ? { stand: "gut" as const, wort: "Verbunden" } : { stand: "schlecht" as const, wort: "Nicht erreichbar" }), text: g?.version ? `Fassung ${g.version}` : "" },
    { ...b.oberflaeche, adresse: location.origin, stand: "gut", wort: "Läuft", text: "Diese Seite" },
  ];
  if (!k) return dienste;
  const kis = wert(ki);
  const gb = wert(gutenberg);
  return [
    ...dienste,
    { ...b.verzeichnis1, ...standAus(!!k.google_books?.aktiviert, q?.google_books ?? null), text: grund(q?.google_books) ?? (k.google_books?.hat_api_key ? "Mit eigenem Schlüssel" : "Ohne eigenen Schlüssel, eingeschränkt") },
    { ...b.verzeichnis2, ...standAus(!!k.openlibrary?.aktiviert, q?.open_library ?? null), text: grund(q?.open_library) ?? `Höchstens ${k.openlibrary?.rate_limit ?? 1} je Sekunde` },
    { ...b.lexikon, ...standAus(!!k.wikipedia?.aktiviert, q?.wikipedia ?? null), text: grund(q?.wikipedia) ?? "Strukturierte Angaben und Auszüge" },
    { ...b.ki, adresse: k.lm_studio?.url ?? "", ...standAus(!!k.lm_studio?.aktiviert, kis ? { erreichbar: kis.erreichbar } : null), text: kis?.erreichbar ? `Modell ${kis.modell}` : (grund(kis) ?? "") },
    { ...b.gutenberg, adresse: gb?.url ?? b.gutenberg.adresse, ...standAus(true, gb), text: gb?.erreichbar ? "Suche antwortet" : (gb?.info || "") },
  ];
}
