// Der Inhalt eines Buchs für den Kinderleser: Einheiten (Seiten eines PDF, Abschnitte eines EPUB, Stücke eines Textes) als Folge
// von Bausteinen mit Wörtern und Bildern. Der Text einer Einheit ist derselbe wie beim Vorlesen im normalen Leser (Absätze durch
// eine Leerzeile getrennt), so passt eine gemerkte Vorlesestelle in beide.
import type { Lesewerte } from "../lesestand";
import { woerterAus } from "./umbruch";
import type { Bild, Einheit, Kinderblock, Kinderstelle } from "./typen";

export type Quellart = "pdf" | "epub" | "txt";

export interface Kinderquelle {
  readonly art: Quellart;
  readonly anzahl: number;
  /** Wie eine Einheit heißt, etwa "Seite 12" */
  name(einheit: number): string;
  einheit(nr: number): Promise<Einheit>;
  /** Der Lesestand in der Form des normalen Lesers */
  lesewerte(stelle: Kinderstelle): Promise<Lesewerte>;
  /** Die Stelle zu einem Lesestand des normalen Lesers; null, wenn er nichts Brauchbares sagt */
  stelleAus(werte: Lesewerte): Promise<Kinderstelle | null>;
  /** Wo eine Markierung hingehört (cfi_range), wie der normale Leser sie schreibt */
  markierungsort(einheit: number, von: number, bis: number): Promise<string>;
  /** Die Einheit einer Markierung; null, wenn sie nicht in diesem Buch zu finden ist */
  einheitDer(markierungsort: string): Promise<number | null>;
  /** Wie eine Stelle für Notizen heißt ("S.12", "40%") */
  ort(stelle: Kinderstelle): string;
  schliesse(): void;
}

/** Ein Stück Text einer Einheit, wie es zum Text beiträgt */
export interface Textstueck {
  art: "titel" | "absatz";
  text: string;
}

export type Stueck = Textstueck | { art: "bild"; bild: Bild };

/** Eine Einheit aus Stücken: Texte werden mit einer Leerzeile verbunden, Bilder stehen an der Stelle, an der sie kommen */
export function einheitAus(nr: number, stuecke: Stueck[]): Einheit {
  const teile: string[] = [];
  const bloecke: Kinderblock[] = [];
  let laenge = 0;
  for (const s of stuecke) {
    if (s.art === "bild") {
      bloecke.push({ art: "bild", von: laenge, bild: s.bild });
      continue;
    }
    const text = s.text.trim();
    if (!text) continue;
    if (teile.length) laenge += 2;
    bloecke.push({ art: s.art, von: laenge, woerter: woerterAus(text, laenge) });
    teile.push(text);
    laenge += text.length;
  }
  return { nr, text: teile.join("\n\n"), bloecke };
}

/** Bausteine aus einem fertigen Text, dessen Absätze eine Leerzeile trennt (Textkarte); Bilder an ihren Stellen */
export function einheitAusText(nr: number, text: string, istTitel: (von: number) => boolean, bilder: { von: number; bild: Bild }[]): Einheit {
  const bloecke: Kinderblock[] = [];
  const absaetze = [...text.matchAll(/(?:(?!\n\n)[\s\S])+/g)];
  for (const a of absaetze) {
    const woerter = woerterAus(a[0], a.index);
    if (woerter.length) bloecke.push({ art: istTitel(woerter[0].von) ? "titel" : "absatz", von: woerter[0].von, woerter });
  }
  for (const b of bilder) bloecke.push({ art: "bild", von: b.von, bild: b.bild });
  // Bilder vor dem Text an derselben Stelle
  bloecke.sort((a, b) => a.von - b.von || (a.art === "bild" ? -1 : 0) - (b.art === "bild" ? -1 : 0));
  return { nr, text, bloecke };
}

/** Wo ein Wortlaut in der Einheit steht; für Markierungen, die nur ihren Wortlaut kennen */
export function lageVon(text: string, wortlaut: string): { von: number; bis: number } | null {
  const gesucht = wortlaut.trim();
  if (!gesucht) return null;
  const i = text.indexOf(gesucht);
  if (i >= 0) return { von: i, bis: i + gesucht.length };
  // Leerraum kann anders sein: über die Wörter suchen
  const muster = new RegExp(gesucht.split(/\s+/).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+"));
  const m = muster.exec(text);
  return m ? { von: m.index, bis: m.index + m[0].length } : null;
}
