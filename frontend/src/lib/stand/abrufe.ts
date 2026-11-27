// Was die Stände von selbst abfragen und welche Fähigkeit (BF-78) der Server dafür verlangt, an einer Stelle: kein Stand ruft
// einen Weg, den das aktive Profil nicht darf (etwa die Stufe Jugend den KI-Weg der Verbindungen). Maßgeblich bleibt der
// Server (braucht(...) an den Wegen); fragt die Oberfläche nicht, antwortet er auch nicht mit 403.
import type { Faehigkeit } from "../api/familie";
import { ich } from "./ich.svelte";

export const ABRUFE = {
  /** GET /api/katalog: Bereiche und Kategorien in Leiste und Buchseite */
  katalog: "katalog",
  /** GET /api/verbindungen: Lämpchen der Dienste, darunter die KI */
  verbindungen: "ki",
  /** GET /api/config/update-check: Hinweis auf eine neue Version */
  neueVersion: "einstellungen",
  /** GET /api/einordnung/stand: Lauf "Art der Werke bestimmen" */
  werkarten: "bearbeiten",
  /** GET /api/books/rescan/status: Ergänzen der Bibliothek */
  ergaenzung: "einstellungen",
  /** GET /api/einrichtung/auftraege: lange Aufträge des Servers (Prüfung, Neuaufbau, Volltexte neu lesen) */
  langeAuftraege: "einstellungen",
  /** GET /api/annahme und ihr Ereignisstrom: Aufnahmen, Einlesen, Zum Bestätigen */
  annahme: "hinzufuegen",
  /** GET /api/fassungen: Übersetzungen in Arbeit */
  uebersetzungen: "ki",
  /** GET /api/collections/{id}/luecken und /api/luecken/*: fehlende Bände in Sammlungen (BF-75); alles dazu erscheint nur damit */
  luecken: "luecken",
} as const satisfies Record<string, Faehigkeit>;

export type Abruf = keyof typeof ABRUFE;

export const darfAbrufen = (abruf: Abruf): boolean => ich.darf(ABRUFE[abruf]);

/** Woraus die Aufträge im Kopf bestehen; ohne eine davon gibt es die Taste nicht */
const AUFTRAGSQUELLEN: readonly Abruf[] = ["annahme", "ergaenzung", "langeAuftraege", "werkarten", "uebersetzungen"];

export const mitAuftraegen = (): boolean => AUFTRAGSQUELLEN.some(darfAbrufen);
