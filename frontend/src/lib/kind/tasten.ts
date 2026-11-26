// Die Tasten des Kinderlesers an einer Stelle: welche es gibt, wie sie heißen, welches Symbol sie tragen und was sie nach dem
// Druck ansagen. Welche erscheinen, entscheiden allein die Fähigkeiten vom Server und die Lesehilfen, die die Eltern erlauben.
import type { Faehigkeit, Kinderdarstellung } from "./typen";

export type Lesetaste = "zurueck" | "merken" | "vorlesen" | "silben" | "zeile" | "stift" | "notiz" | "weiter";

/** Wie es gerade steht: Vorlesen läuft oder ruht, die Schalter sind an oder aus */
export interface Tastenstand {
  vorlesen: "aus" | "laeuft" | "ruht";
  silben: boolean;
  zeile: boolean;
  stift: boolean;
  gemerkt: boolean;
}

export interface Tastenbild {
  name: string;
  symbol: string;
  /** Voll gezeichnetes oder nur umrissenes Symbol */
  voll: boolean;
  an: boolean;
}

/** Die Tasten in ihrer Reihenfolge, nur die erlaubten */
export function lesetasten(f: ReadonlySet<Faehigkeit>, d: Pick<Kinderdarstellung, "silben" | "lesezeile">, kannVorlesen: boolean): Lesetaste[] {
  const aus: Lesetaste[] = ["zurueck"];
  if (f.has("lesezeichen")) aus.push("merken");
  if (kannVorlesen && f.has("vorlesen")) aus.push("vorlesen");
  if (d.silben) aus.push("silben");
  if (d.lesezeile) aus.push("zeile");
  if (f.has("markierungen")) aus.push("stift");
  if (f.has("notizen")) aus.push("notiz");
  aus.push("weiter");
  return aus;
}

/** Name und Symbol einer Taste im jetzigen Stand */
export function tastenbild(t: Lesetaste, s: Tastenstand): Tastenbild {
  switch (t) {
    case "zurueck":
      return { name: "Zurück", symbol: "arrow-left", voll: true, an: false };
    case "weiter":
      return { name: "Weiter", symbol: "arrow-right", voll: true, an: false };
    case "merken":
      return { name: "Merken", symbol: "bookmark", voll: s.gemerkt, an: s.gemerkt };
    case "vorlesen":
      if (s.vorlesen === "laeuft") return { name: "Pause", symbol: "pause", voll: true, an: true };
      if (s.vorlesen === "ruht") return { name: "Weiter hören", symbol: "play", voll: true, an: true };
      return { name: "Vorlesen", symbol: "volume-high", voll: true, an: false };
    case "silben":
      return { name: "Silben", symbol: "palette", voll: true, an: s.silben };
    case "zeile":
      return { name: "Zeile", symbol: "grip-lines", voll: true, an: s.zeile };
    case "stift":
      return { name: "Stift", symbol: "highlighter", voll: true, an: s.stift };
    case "notiz":
      return { name: "Notiz", symbol: "note-sticky", voll: true, an: false };
  }
}

/**
 * Was eine Taste ansagt; s ist der Stand nach ihrer Wirkung. Schalter sagen, wie sie nun stehen; die Taste Vorlesen sagt,
 * was jetzt geschieht: anfangen ("Vorlesen"), anhalten ("Pause"), weiterhören ("Weiter").
 */
export function tastenansage(t: Lesetaste, s: Tastenstand, vorlesenVorher: Tastenstand["vorlesen"] = s.vorlesen): string {
  switch (t) {
    case "vorlesen":
      if (s.vorlesen === "ruht") return "Pause";
      return vorlesenVorher === "ruht" ? "Weiter" : "Vorlesen";
    case "silben":
      return s.silben ? "Silben an" : "Silben aus";
    case "zeile":
      return s.zeile ? "Zeile an" : "Zeile aus";
    case "stift":
      return s.stift ? "Stift an" : "Stift aus";
    case "merken":
      return s.gemerkt ? "Gemerkt" : "Lesezeichen weg";
    default:
      return tastenbild(t, s).name;
  }
}

/** Steuert die Taste den Vorlesestrom selbst? Nur sie wird während des Vorlesens angesagt */
export const steuertVorlesen = (t: Lesetaste): boolean => t === "vorlesen" || t === "weiter" || t === "zurueck";
