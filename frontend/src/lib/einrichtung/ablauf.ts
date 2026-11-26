// Ablauf des Assistenten der Ersteinrichtung (BF-82), ohne Oberfläche: welche Ausgangslage, welche Schritte man sieht, wie sie
// im Fortschritt heißen, wohin Zurück und Weiter führen und was die Übersicht am Ende zeigt. Welche Schritte es gibt und ob sie
// erledigt sind, sagt allein der Server (schritte.json); hier steht nur, wie die Oberfläche sie zeigt (Entwurf einrichtung-1).
import type { Anschluss, Einrichtung, Katalogwahl, Lagename, Schritt } from "../api/einrichtung";

/** Wie der Assistent läuft: eine der vier Ausgangslagen oder unter Wartung wieder geöffnet */
export type Lauf = Lagename | "wartung";

export interface Lagebild {
  titel: string;
  text: string;
  symbol: string;
  farbe: string;
}

/** Die vier Ausgangslagen als Kacheln, in dieser Folge */
export const LAGEN: [Lagename, Lagebild][] = [
  ["neu", { titel: "Neu beginnen", text: "Konto und Speicherorte, dann alles Weitere nach Wunsch.", symbol: "seedling", farbe: "#3f8f5a" }],
  ["sicherung", { titel: "Aus Sicherung wiederherstellen", text: "Aus einer Datei, dem Sicherungsordner oder der Kellerwolke.", symbol: "clock-rotate-left", farbe: "#2f6fb3" }],
  ["kellerwolke", { titel: "Ablage in der Kellerwolke übernehmen", text: "Die Bibliothek neu aufbauen, aus dem Auszug je Buch.", symbol: "cloud", farbe: "#5b5fb3" }],
  ["umzug", { titel: "Umzug von anderer Installation", text: "Mit Adresse und Einmalcode vom alten Gerät.", symbol: "truck-ramp-box", farbe: "#a87a2a" }],
];

export const WILLKOMMEN = "Willkommen bei BücherFreunde";

/** Überschrift im Kopf des Assistenten */
export function lagetitel(lauf: Lauf | null): string {
  if (lauf === "wartung") return "Einrichtung";
  return LAGEN.find(([l]) => l === lauf)?.[1].titel ?? WILLKOMMEN;
}

/**
 * Die Stationen im Fortschritt mit ihren kurzen Namen; ein Schritt ohne Station gehört zum Ende (der Fortschritt steht dann
 * ganz auf fertig).
 */
export const STATIONEN: Record<Lauf, Record<string, string>> = {
  neu: { konto: "Konto", orte: "Orte", anschluesse: "Anschlüsse", katalog: "Katalog", familie: "Familie", buecher: "Bücher" },
  sicherung: { orte: "Orte", sicherung: "Sicherung", pruefung: "Prüfen", abschluss: "Bericht" },
  kellerwolke: { konto: "Konto", orte: "Orte", ordner: "Ordner", neuaufbau: "Neuaufbau", abschluss: "Bericht" },
  umzug: { verbinden: "Verbinden", orte: "Orte", originale: "Originale", pruefung: "Übernahme" },
  wartung: { orte: "Orte", anschluesse: "Anschlüsse", katalog: "Katalog", familie: "Familie", buecher: "Bücher" },
};

const TITEL: Record<string, string> = {
  konto: "Konto",
  orte: "Speicherorte",
  anschluesse: "Anschlüsse",
  katalog: "Katalog",
  familie: "Familie und Kinder",
  buecher: "Erste Bücher",
  sicherung: "Sicherung wählen",
  pruefung: "Originale prüfen",
  ordner: "Ordner der Bücher",
  neuaufbau: "Neuaufbau",
  verbinden: "Verbinden",
  originale: "Originale",
  abschluss: "Fertig",
};

/** Am Ende steht je nach Lauf etwas anderes: die Übersicht, der Bericht oder die Änderungen zum Übernehmen */
const ABSCHLUSS: Partial<Record<Lauf, string>> = { sicherung: "Bericht", kellerwolke: "Bericht", umzug: "Bericht", wartung: "Übernehmen" };

export function schritttitel(lauf: Lauf, schritt: string): string {
  return (schritt === "abschluss" && ABSCHLUSS[lauf]) || TITEL[schritt] || schritt;
}

export function laufVon(e: Einrichtung): Lauf | null {
  return e.modus === "wartung" ? "wartung" : e.ausgangslage;
}

/** Was man sieht: entfallene Schritte (Originale mit Kellerwolke) nicht */
export function sichtbar(schritte: readonly Schritt[]): Schritt[] {
  return schritte.filter((s) => s.stand !== "entfaellt");
}

/** Der gezeigte Schritt: der gewählte, sonst der erste offene des Servers, sonst der letzte */
export function aktueller(schritte: readonly Schritt[], gezeigt: string, offen: string | null): Schritt | null {
  return schritte.find((s) => s.schluessel === gezeigt) ?? schritte.find((s) => s.schluessel === offen) ?? schritte.at(-1) ?? null;
}

/** Der Schritt davor (-1) oder danach (1); null am Rand */
export function nachbar(schritte: readonly Schritt[], von: string, richtung: 1 | -1): string | null {
  const n = schritte.findIndex((s) => s.schluessel === von);
  return n < 0 ? null : (schritte[n + richtung]?.schluessel ?? null);
}

export type Stationsart = "fertig" | "jetzt" | "wartet" | "";

export interface Station {
  schluessel: string;
  name: string;
  art: Stationsart;
}

export interface Fortschritt {
  stationen: Station[];
  /** Die wievielte Station gerade dran ist; null am Ende */
  nummer: number | null;
  fertig: boolean;
}

export const STATIONSWORT: Record<Stationsart, string> = { wartet: "übersprungen", fertig: "fertig", jetzt: "jetzt", "": "offen" };

export function fortschritt(lauf: Lauf, schritte: readonly Schritt[], jetzt: string): Fortschritt {
  const namen = STATIONEN[lauf];
  const liste = sichtbar(schritte).filter((s) => namen[s.schluessel]);
  const n = liste.findIndex((s) => s.schluessel === jetzt);
  const fertig = n < 0;
  const art = (s: Schritt, k: number): Stationsart =>
    s.stand === "uebersprungen" && k !== n ? "wartet" : k === n ? "jetzt" : fertig || k < n || s.stand === "erledigt" ? "fertig" : "";
  return { stationen: liste.map((s, k) => ({ schluessel: s.schluessel, name: namen[s.schluessel], art: art(s, k) })), nummer: fertig ? null : n + 1, fertig };
}

/** "Pflicht" steht nur dort, wo sich andere Schritte überspringen lassen */
export function zeigtPflicht(schritte: readonly Schritt[], schritt: Schritt): boolean {
  return schritt.pflicht && schritt.schluessel !== "abschluss" && schritte.some((s) => !s.pflicht);
}

/** Der Server nennt die Wahl im Katalog als Satz (einrichtung/katalog_schritt.py) */
export const KATALOGWAHL: Record<Katalogwahl, string> = {
  standard: "Mitgelieferter Katalog",
  leer: "Leer begonnen",
  bestand: "Mitgelieferter Katalog, Vorschlag aus dem Bestand",
};

export function katalogwahlAus(text: string): Katalogwahl | null {
  return (Object.entries(KATALOGWAHL) as [Katalogwahl, string][]).find(([, t]) => t === text)?.[0] ?? null;
}

/** Wohin eine Zeile der Übersicht führt: Name der Einstellung und Adresse */
export const ZIELE: Record<string, [string, string]> = {
  orte: ["Verbindungen", "/settings/verbindungen"],
  anschluesse: ["Verbindungen", "/settings/verbindungen"],
  katalog: ["Katalog", "/settings/katalog"],
  familie: ["Familie", "/settings/familie"],
  buecher: ["Hinzufügen", "/import"],
};

export interface Uebersichtszeile {
  schluessel: string;
  name: string;
  text: string;
  ziel: [string, string] | null;
}

export interface Uebersicht {
  eingerichtet: Uebersichtszeile[];
  uebersprungen: Uebersichtszeile[];
}

/**
 * Was eingerichtet und was übersprungen ist. Die Anschlüsse stehen einzeln da, jeder mit seiner Adresse; hat keiner eine, steht
 * der Schritt als eine Zeile unter den übersprungenen.
 */
export function uebersicht(schritte: readonly Schritt[], anschluesse: readonly Anschluss[]): Uebersicht {
  const aus: Uebersicht = { eingerichtet: [], uebersprungen: [] };
  for (const s of sichtbar(schritte)) {
    if (s.schluessel === "abschluss") continue;
    const ziel = ZIELE[s.schluessel] ?? null;
    if (s.schluessel === "anschluesse" && anschluesse.some((a) => a.adresse)) {
      for (const a of anschluesse) {
        const zeile = { schluessel: `anschluss-${a.art}`, name: a.name, text: a.adresse || "nicht eingerichtet", ziel };
        (a.adresse ? aus.eingerichtet : aus.uebersprungen).push(zeile);
      }
      continue;
    }
    if (s.schluessel === "anschluesse") {
      aus.uebersprungen.push({ schluessel: s.schluessel, name: s.name, text: anschluesse.map((a) => a.name).join(", ") || s.text, ziel });
      continue;
    }
    (s.stand === "erledigt" ? aus.eingerichtet : aus.uebersprungen).push({ schluessel: s.schluessel, name: s.name, text: s.text, ziel });
  }
  return aus;
}

/** Wozu ein Ort dient, neben seinem Namen (einrichtung/orte.py nennt die Kennung) */
export const ORTSZWECK: Record<string, string> = {
  bestand: "Datenbank und Sicherungen",
  texte: "ohne Kellerwolke auch die Originale",
  suche: "jederzeit neu zu bauen",
  zwischen: "Originale auf Zeit",
};

/** Wie Weiter in einem Schritt heißt und was es tut; ohne `tun` gilt der Schritt als erledigt und der nächste kommt */
export interface Weiterwahl {
  text?: string;
  symbol?: string;
  gesperrt?: boolean;
  titel?: string;
  tun?: () => Promise<unknown>;
}

/** Zeichen der Teile eines Auftrags, in der Folge des Servers; Teile ohne Zeichen stehen nicht einzeln da */
export const TEILZEICHEN: Record<string, Record<string, string>> = {
  einspielen: { holen: "download", pruefen: "stethoscope", vorher: "floppy-disk", einspielen: "database", danach: "arrows-rotate" },
  neuaufbau: { buecher: "book", angaben: "rectangle-list", volltext: "font", umschlaege: "images", persoenliches: "user-pen" },
};
