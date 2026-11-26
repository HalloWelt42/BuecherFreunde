// Quellen und Dienste: was sie liefern, welche Felder daraus werden, und ihr gemerkter Stand
import { kiStatus } from "../../lib/api/ai";
import { healthCheck } from "../../lib/api/config";
import type { Quellenstand } from "../../lib/api/metadata";
import { anzahl, zahl } from "../../lib/format";
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
  /** eine Quelle, die sich auf Wunsch echt prüfen lässt */
  quelle?: boolean;
  /** Anfragen heute und Gemerktes */
  zahlen?: string;
}

type Beschreibung = Pick<Dienst, "kennung" | "name" | "symbol" | "beschreibung" | "felder" | "autoren" | "konfidenz" | "roh">;

const MARC: Zuordnung[] = [["245 a, n, p, b", "Titel und Untertitel"], ["100, 700 (Rolle aut, edt)", "Autor"], ["264 b, c", "Verlag, Jahr"], ["300 a", "Seiten"], ["020", "ISBN"], ["041, 008", "Sprache"], ["082, 084 (Sachgruppe)", "Regale"], ["650, 651, 655 (Normdatei)", "Regale"], ["520", "Beschreibung"]];
const MARC_ROH = ["auflage", "reihe", "umfang", "notationen", "freie_schlagworte", "verweise", "herausgeber"];

const beschreibungen: Record<string, Beschreibung> = {
  server: { kennung: "server", name: "Server", symbol: "server", beschreibung: "Verwaltet Bücher, Regale, Suche, Aufnahme und Einstellungen und liefert alles über eine Schnittstelle aus.", felder: [] },
  oberflaeche: { kennung: "oberflaeche", name: "Oberfläche", symbol: "display", beschreibung: "Diese Seite. Spricht nur mit dem Server.", felder: [] },
  google_books: {
    kennung: "google_books", name: "Verzeichnis 1", symbol: "book-atlas",
    beschreibung: "Titel, Autor, Verlag, ISBN, Beschreibung, Umschlag und Kategorien. Antwortet nur mit eigenem Schlüssel (GOOGLE_BOOKS_API_KEY in der .env); ohne ihn wird sie nie gefragt.",
    felder: [["volumeInfo.title", "Titel"], ["volumeInfo.authors", "Autor"], ["volumeInfo.publisher", "Verlag"], ["volumeInfo.publishedDate", "Jahr"], ["volumeInfo.pageCount", "Seiten"], ["volumeInfo.industryIdentifiers", "ISBN"], ["volumeInfo.language", "Sprache"], ["volumeInfo.description", "Beschreibung"], ["volumeInfo.categories", "Regale"], ["volumeInfo.imageLinks", "Umschlag"]],
    roh: ["untertitel", "erscheinungsdatum", "identifiers", "lesemodi", "altersfreigabe", "inhaltsversion", "vorschau_link", "info_link", "google_books_link", "durchschnittsbewertung", "anzahl_bewertungen", "abmessungen"],
  },
  open_library: {
    kennung: "open_library", name: "Verzeichnis 2, Open Library", symbol: "book-open",
    beschreibung: "Offene Bibliotheksdatenbank mit Umschlägen, Themen und Verweisen. Höchstens eine Anfrage je Sekunde (OPENLIBRARY_RATE_LIMIT); lange Läufe fragen 40 Bücher auf einmal. Umschläge über die ISBN gibt es auch für Funde anderer Quellen.",
    felder: [["title", "Titel"], ["authors[].name", "Autor"], ["publishers[].name", "Verlag"], ["publish_date", "Jahr"], ["number_of_pages", "Seiten"], ["identifiers", "ISBN"], ["subjects (erste 12)", "Regale"], ["cover.large", "Umschlag"]],
    roh: ["identifiers", "excerpts", "links", "subjects", "subject_places", "subject_people", "subject_times"],
  },
  dnb: {
    kennung: "dnb", name: "Verzeichnis 3, Deutsche Nationalbibliothek", symbol: "building-columns",
    beschreibung: "Jedes in Deutschland erschienene Buch seit 1913, mit Sachgruppe, Schlagworten, Auflage und der Kennung des Autors in der Normdatei. Die beste Quelle für deutsche Fach- und Sachbücher und Romane. Ohne Anmeldung, Angaben frei.",
    felder: MARC, roh: MARC_ROH,
  },
  k10plus: {
    kennung: "k10plus", name: "Verzeichnis 4, K10plus", symbol: "layer-group",
    beschreibung: "Gemeinsamer Katalog vieler Hochschul- und Landesbibliotheken: auch englische Fachbücher, ältere und vergriffene Bücher, oft mit Inhaltsangabe. Ohne Anmeldung, Angaben frei.",
    felder: MARC, roh: MARC_ROH,
  },
  crossref: {
    kennung: "crossref", name: "Verzeichnis 5, Crossref", symbol: "file-lines",
    beschreibung: "Fachartikel, Tagungsbände und viele Fachbücher mit DOI. Steht eine DOI auf den ersten Seiten einer PDF, findet sie das Werk darüber, sonst über ISBN oder Titel.",
    felder: [["title, subtitle", "Titel und Untertitel"], ["author", "Autor"], ["publisher", "Verlag"], ["issued", "Jahr"], ["ISBN", "ISBN"], ["DOI", "DOI"], ["language", "Sprache"], ["abstract", "Beschreibung"]],
    roh: ["art", "zeitschrift", "band", "heft", "seitenbereich", "issn", "verweis", "herausgeber"],
  },
  wikipedia: {
    kennung: "wikipedia", name: "Lexikon, Wikipedia", symbol: "landmark",
    beschreibung: "Strukturierte Angaben und Beschreibungen. Bücher über die ISBN oder Titel und Autor, Autoren über die Normdatei oder den Namen, mit Punkten für jede Übereinstimmung. Ohne Kontaktangabe (QUELLEN_KONTAKT) höchstens neun Anfragen je Minute.",
    felder: [["labels (de/en), P1476", "Titel"], ["P50 (Autor)", "Autor"], ["P123 (Verlag)", "Verlag"], ["P577 (Erscheinungsdatum)", "Jahr"], ["P1104 (Seitenanzahl)", "Seiten"], ["P212/P957 (ISBN mit Strichen)", "ISBN"], ["P407 (Sprache)", "Sprache"], ["Einleitung und Inhalt des Artikels", "Beschreibung"], ["P136 (Genre) und P921 (Thema)", "Regale"]],
    autoren: [["Kennung der Normdatei aus der ISBN eines Buchs", "sicher, 30 Punkte"], ["ISBN in Werken", "30 Punkte"], ["P800 (Werke) gegen Bibliothek", "15 Punkte"], ["P106 (Beruf Schriftsteller)", "10 Punkte, Fachberuf 6"], ["Gleicher Name", "8 Punkte"], ["Eintrag in dewiki", "5 Punkte"], ["Zahl der Einträge", "1 bis 10 Punkte"], ["dewiki Volltext", "Lebenslauf"], ["P18 (Bild)", "Foto in drei Größen"], ["P800 (bekannte Werke)", "Werkliste"], ["P27 (Staatsangehörigkeit)", "Land"], ["P569/P570 (Geburt und Tod)", "Lebensdaten"], ["P227, P214, P213, P496", "Verweise GND, VIAF, ISNI, ORCID"]],
    konfidenz: "Sicher: über ein Buch der Bibliothek belegt (Normdatei, Werk, ISBN oder im Artikel genannt), oder als einziger Mensch dieses Namens ab 15 Punkten. Wahrscheinlich: ab 8 Punkten. Unsicher: darunter.",
    roh: ["wikidata_id", "kurzbeschreibung", "isbn13", "isbn10", "autoren", "verlage", "sprachen", "genres", "themen", "typen", "wikipedia_titel", "sitelinks"],
  },
  gnd: {
    kennung: "gnd", name: "Normdatei, GND", symbol: "id-card",
    beschreibung: "Wer ein Autor ist: eindeutige Kennung, Lebensdaten, Beruf, kurze Biografie und Verweise auf VIAF, ISNI und Wikidata. Steht der Autor eines Buchs mit ISBN im Katalog, ist der Treffer sicher.",
    felder: [], autoren: [["preferredName", "Name"], ["dateOfBirth, dateOfDeath", "Lebensdaten"], ["biographicalOrHistoricalInformation, professionOrOccupation", "Beschreibung"], ["geographicAreaCode", "Land"], ["sameAs", "Verweise VIAF, ISNI, Wikidata"], ["wikipedia", "Wikipedia"]],
  },
  gutenberg: {
    kennung: "gutenberg", name: "Gutenberg", symbol: "landmark-dome",
    beschreibung: "Gemeinfreie Bücher: suchen nach Titel, Autor und Sprache, ansehen und als EPUB oder Text übernehmen. Gesucht wird über Gutendex, die Dateien kommen von den Spiegeln des Project Gutenberg.",
    felder: [["id", "Nummer"], ["title", "Titel"], ["authors[].name", "Autor"], ["languages[]", "Sprachen"], ["formats (epub/txt)", "Datei"], ["formats (image/jpeg)", "Umschlag"], ["bookshelves[]", "Regale"], ["subjects[]", "Themen"], ["download_count", "Zahl der Downloads"]],
    roh: ["gutenberg_id", "sprachen", "regale", "themen"],
  },
  ki: { kennung: "ki", name: "KI", symbol: "robot", beschreibung: "Liest Titel, Autor und einen Textauszug und schlägt Regale mit Wahrscheinlichkeit vor.", felder: [["Auswertung", "Regale, Vorschläge mit Konfidenz"]] },
};

const LEER: Beschreibung = { kennung: "", name: "", symbol: "plug", beschreibung: "", felder: [] };

/** Zahlen eines Tages, nur was es gibt */
export function zahlenText(q: Quellenstand): string {
  const teile = [q.anfragen_heute ? `Heute ${anzahl(q.anfragen_heute, "Anfrage", "Anfragen")}${q.hintergrund_heute ? `, ${zahl(q.hintergrund_heute)} im Hintergrund (höchstens ${zahl(q.tagesgrenze)})` : ""}` : "Heute keine Anfrage"];
  if (q.gemerkt) teile.push(anzahl(q.gemerkt, "Antwort gemerkt", "Antworten gemerkt"));
  return teile.join(", ");
}

/** Aus dem gemerkten Stand einer Quelle ein Dienst; nichts davon fragt die Quelle */
export function alsDienst(q: Quellenstand): Dienst {
  const b = beschreibungen[q.kennung] ?? { ...LEER, kennung: q.kennung, name: q.name };
  return { ...b, adresse: q.adresse, stand: q.stand, wort: q.wort, text: q.grund, quelle: true, zahlen: q.aktiv ? zahlenText(q) : "" };
}

/** Server und KI werden gefragt; Quellen kommen aus dem Gemerkten */
export async function pruefeDienste(quellen: Quellenstand[]): Promise<Dienst[]> {
  const [gesund, ki] = await Promise.allSettled([healthCheck(), kiStatus()]);
  const g = gesund.status === "fulfilled" ? (gesund.value as { version?: string }) : null;
  const b = beschreibungen;
  const dienste: Dienst[] = [
    { ...b.server, adresse: `${location.origin}/api`, ...(g ? { stand: "gut" as const, wort: "Verbunden" } : { stand: "schlecht" as const, wort: "Nicht erreichbar" }), text: g?.version ? `Fassung ${g.version}` : "" },
    { ...b.oberflaeche, adresse: location.origin, stand: "gut", wort: "Läuft", text: "Diese Seite" },
  ];
  // Die KI kommt über die Leitstelle; ohne deren Einrichtung ist sie aus
  const kis = ki.status === "fulfilled" ? ki.value : null;
  const kiStand: Pick<Dienst, "stand" | "wort"> = !kis ? { stand: "schlecht", wort: "Nicht erreichbar" } : !kis.aktiviert ? { stand: "aus", wort: "Aus" } : kis.erreichbar ? { stand: "gut", wort: "Verbunden" } : { stand: "schlecht", wort: "Nicht bereit" };
  return [...dienste, ...quellen.map(alsDienst), { ...b.ki, adresse: kis?.url ?? "", ...kiStand, text: kis?.erreichbar ? `Modell ${kis.modell}` : kis?.grund ?? "" }];
}
