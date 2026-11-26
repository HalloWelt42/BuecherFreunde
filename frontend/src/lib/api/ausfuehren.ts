// Ausführen (BF-29): was die Sandbox der Codeschmiede kann, der Lauf eines Listings als Aufzeichner der Debug-Sitzung
// und je PHP-Fassung die eingebauten Funktionen. Gerechnet wird nie hier, sondern über das eigene Backend in der Sandbox.
// Nur Typen aus dem Appkern: dieser Teil liegt im Bau der Startseite, Editor und Debugger kommen erst mit dem Fenster.
import type { Aufzeichner, Debuglauf } from "appkern-oberflaeche/code";
import { get, post } from "./client";

/** Sprachen, die das Fenster ausführt; was davon gerade läuft, sagt der Stand der Sandbox */
export type Codesprache = "python" | "javascript" | "php";

export const CODESPRACHEN: readonly Codesprache[] = ["python", "javascript", "php"];

/** Was die Sandbox für eine Sprache kann: die Fassungen (neueste zuerst; leer: keine Wahl) und ob sie den Lauf
 *  aufzeichnet (sonst nur ausführen, ohne Debugger). */
export interface Sprachangebot {
  sprache: Codesprache;
  fassungen: string[];
  aufzeichnen: boolean;
}

export interface Ausfuehrstand {
  bereit: boolean;
  sprachen: Sprachangebot[];
  /** Warum es nicht geht (nicht erreichbar, nicht zugelassen); leer, wenn bereit */
  grund: string;
}

/** Ein Lauf, wie das Fenster ihn zeigt; ohne Aufzeichnung leere Schritte, dazu die Hinweise (Warnungen) */
export type Lauf = Debuglauf & { hinweise?: string };

export const SPRACHNAMEN: Record<Codesprache, string> = { python: "Python", javascript: "JavaScript", php: "PHP" };
export const SPRACHSYMBOLE: Record<Codesprache, string> = { python: "python", javascript: "js", php: "php" };
export const ENDUNGEN: Record<Codesprache, string> = { python: "py", javascript: "js", php: "php" };

let stand: Promise<Ausfuehrstand> | null = null;

/** Ob und was die Sandbox gerade kann; einmal je Sitzung der Seite gefragt, ein Fehler gilt als "nicht bereit" und
 *  wird beim nächsten Mal neu gefragt. */
export function ausfuehrstand(): Promise<Ausfuehrstand> {
  stand ??= get<Ausfuehrstand>("/api/ausfuehren").catch((f) => {
    stand = null;
    return { bereit: false, sprachen: [], grund: f instanceof Error ? f.message : String(f) };
  });
  return stand;
}

/** Aufzeichner der Debug-Sitzung: der Lauf in der Sandbox (in der Fassung, wo es eine Wahl gibt); geht es nicht, wird
 *  der Grund zur Meldung der Sitzung. */
export function laufIn(sprache: Codesprache, fassung: string): Aufzeichner {
  return async (code) => {
    const antwort = await post<{ aufzeichnung: Lauf | null; grund: string }>("/api/ausfuehren", { code, sprache, fassung, eingabe: [] });
    if (!antwort.aufzeichnung) throw new Error(antwort.grund || "Der Lauf kam ohne Ergebnis zurück");
    return antwort.aufzeichnung;
  };
}

let funktionen: Promise<Record<string, string[]>> | null = null;

/** Je PHP-Fassung die eingebauten Funktionen (klein geschrieben); einmal je Sitzung der Seite gefragt. */
export function phpFunktionen(): Promise<Record<string, string[]>> {
  funktionen ??= get<Record<string, string[]>>("/api/ausfuehren/funktionen/php")
    .then((b) => {
      if (!Object.keys(b).length) funktionen = null; // noch kein Bestand: beim nächsten Öffnen neu fragen
      return b;
    })
    .catch(() => {
      funktionen = null;
      return {};
    });
  return funktionen;
}

// Codestellen eines Buchs (Begleiter codestellen.json des Servers): Lage je Teil, Code, Sprache und die Vorprüfung

/** Ein Stück einer Stelle. PDF: Dateiseite und Rechteck [x0, y0, x1, y1] in Punkten oben links; EPUB: Kapitel und Nummer
 *  des Codeblocks darin; Markdown und Text: Zeile */
export interface Codeteil {
  seite: number | null;
  rechteck: [number, number, number, number] | null;
  offen_oben: boolean;
  offen_unten: boolean;
  kapitel: string | null;
  nr: number | null;
  zeile: number | null;
}

/** laeuft: lief für sich (mit Ausgabe); auszug: braucht mehr, mit kurzem Grund; offen: noch nicht geprüft */
export interface Vorpruefung {
  stand: "laeuft" | "auszug" | "offen";
  quelle: "lauf" | "ki" | "";
  ausgabe: string;
  fehler: string;
  grund: string;
  fehlt: string[];
  geprueft_am: string;
}

export interface Codestelle {
  kennung: string;
  teile: Codeteil[];
  sprache: string | null;
  sicherheit: number;
  quelle: string;
  titel: string;
  datei: string;
  code: string;
  zeilennummern_ab: number | null;
  pruefsumme: string;
  /** Sprache der Sandbox mit sicherem Befund, die Sandbox antwortet: dann gibt es die Taste */
  ausfuehrbar: boolean;
  vorpruefung: Vorpruefung | null;
}

export interface Codestellen {
  buch: number;
  /** ausstehend: die Erkennung kommt gleich dran; ohne: das Format hat keine Codeblöcke */
  stand: "erkannt" | "ausstehend" | "ohne";
  format: string | null;
  grund: string;
  anzahl: number;
  stellen: Codestelle[];
}

/** Die Stellen eines Buchs; im PDF auf Wunsch nur die, die in die Seiten von bis bis reichen (Ketten ganz) */
export const holeCodestellen = (buch: number, von?: number, bis?: number): Promise<Codestellen> =>
  get(`/api/books/${buch}/codestellen`, { von, bis });

export const istCodesprache = (s: string | null): s is Codesprache => s === "python" || s === "javascript" || s === "php";
