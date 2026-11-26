// Wie eine Übersetzung in der Oberfläche heißt (BF-71, Entwurf "Bücher übersetzen"): Flaggenlabels, Stationen, Kapitel,
// Befunde, der Auftrag. Eine Stelle für alle Ansichten.
import { anzahl, sprache, zahl } from "../format";
import type { Befund, Fassungseintrag, Kapitelstand, Laufeintrag, Laufstand, Station, Stationsname, Zahlen } from "./typen";
import { dauer, gegen, ungefaehr } from "./zeiten";

/** Formate, die schon übersetzt werden (wie FORMATE in backend/app/services/fassungsstand.py) */
export const UEBERSETZBAR = ["epub"];

/** Name und Stand eines Flaggenlabels */
export function labeltext(f: Fassungseintrag, seiten: number): { name: string; stand: string } {
  if (f.original) return { name: sprache(f.sprache) || "Original", stand: seiten ? `Original, ${zahl(seiten)} Seiten` : "Original" };
  const name = sprache(f.sprache);
  const kapitel = f.kapitel_gesamt ? `${zahl(f.kapitel_fertig)} von ${anzahl(f.kapitel_gesamt, "Kapitel", "Kapiteln")}` : "";
  switch (f.stand) {
    case "fertig":
      return { name, stand: "von uns übersetzt, fertig" };
    case "laeuft":
      return { name, stand: [kapitel || "beginnt", f.fertig_gegen && kapitel ? `fertig ${gegen(f.fertig_gegen)}` : ""].filter(Boolean).join(", ") };
    case "pause":
      return { name, stand: ["Pause", kapitel].filter(Boolean).join(", ") };
    case "teilweise":
      return { name, stand: ["abgebrochen", kapitel].filter(Boolean).join(", ") };
    default:
      return { name, stand: ["Fehler", kapitel].filter(Boolean).join(", ") };
  }
}

/** Zeichen je Station, wenn sie läuft; fertig ist ein Haken, wartend eine Uhr */
export const STATIONSZEICHEN: Record<Stationsname, string> = {
  Zerlegen: "scissors", Begriffe: "spell-check", Übersetzen: "language", Prüfen: "list-check", Nacharbeit: "rotate", Setzen: "book",
};

const STATIONSSTAND: Record<Station["stand"], string> = { wartet: "wartet", laeuft: "läuft", fertig: "fertig" };

/** Was unter einer Station steht; vom Ort der Ablage nur der Name der Datei (der ganze Pfad steht im Hinweis) */
export function stationstext(s: Station): string {
  if (!s.text) return STATIONSSTAND[s.stand];
  const abgelegt = s.text.match(/^Abgelegt: (.*)$/);
  return abgelegt ? `Abgelegt: ${abgelegt[1].split("/").pop()}` : s.text;
}

/** "Kapitel 8 von 12, Block 41 von 104": wo der Lauf gerade ist */
export function laufort(s: Laufstand): string {
  const k = s.kapitel.find((x) => x.nr === s.kapitel_jetzt);
  if (!k) return "";
  const nr = s.kapitel.indexOf(k) + 1;
  return `Kapitel ${zahl(nr)} von ${zahl(s.kapitel.length)}, Block ${zahl(Math.min(k.bloecke, k.fertig + 1))} von ${zahl(k.bloecke)}`;
}

/** Anteil der Blöcke mit Ergebnis; 0 vor dem Zerlegen */
export function laufanteil(s: Laufstand): number {
  const alle = s.kapitel.reduce((n, k) => n + k.bloecke, 0);
  return alle ? s.kapitel.reduce((n, k) => n + k.fertig, 0) / alle : 0;
}

export function kapitelstandtext(k: Kapitelstand): string {
  if (k.stand === "laeuft") return `läuft, ${zahl(k.fertig)} von ${zahl(k.bloecke)}`;
  return k.stand === "fertig" ? "fertig" : "wartet";
}

/** Dauer eines Kapitels: gemessen, oder geschätzt mit "etwa" */
export function kapiteldauer(k: Pick<Kapitelstand, "dauer_s" | "geschaetzt">): string {
  return k.geschaetzt ? ungefaehr(k.dauer_s) : dauer(k.dauer_s);
}

/** Die Kapitel für die Liste: alle bis zum ersten wartenden, die weiteren wartenden als eine Zeile ("10 bis 12") */
export function kapitelzeilen(kapitel: Kapitelstand[]): { einzeln: Kapitelstand[]; rest: { von: number; bis: number; dauer_s: number } | null } {
  const erster = kapitel.findIndex((k) => k.stand === "wartet");
  const ab = erster < 0 ? kapitel.length : erster + 1;
  const danach = kapitel.slice(ab);
  if (danach.length < 2 || danach.some((k) => k.stand !== "wartet")) return { einzeln: kapitel, rest: null };
  return { einzeln: kapitel.slice(0, ab), rest: { von: ab + 1, bis: kapitel.length, dauer_s: danach.reduce((n, k) => n + k.dauer_s, 0) } };
}

const BEFUNDART: Record<string, string> = {
  marken: "Marken", zahlen: "Zahlen", einheiten: "Einheiten", bezeichner: "Bezeichner", begriffe: "Begriff", sprache: "Sprache",
  laenge: "Länge", vollstaendigkeit: "Vollständigkeit", zeichen: "Zeichen", antwort: "Antwort", sinn: "Sinn", ausgelassen: "Ausgelassen",
  hinzugefuegt: "Hinzugefügt", begriff: "Begriff", grammatik: "Grammatik", pruefer: "Prüfer",
};

/** "Begriff", "Sinn (KI-Prüfer)" */
export function befundname(b: Befund): string {
  const art = BEFUNDART[b.art] ?? b.art;
  return b.quelle === "ki" ? `${art} (KI-Prüfer)` : art;
}

export function befundzeichen(b: Befund): string {
  if (b.quelle === "ki") return "robot";
  return b.art === "begriffe" ? "spell-check" : "list-check";
}

/** Die Zahlen des Prüfberichts als Marken: geprüft, nachgearbeitet, offen */
export function berichtsmarken(z: Zahlen): { text: string; ton: "gut" | "info" | "warn"; symbol: string }[] {
  return [
    { text: `${zahl(z.bestanden)} geprüft`, ton: "gut", symbol: "circle-check" },
    { text: `${zahl(z.nachgearbeitet)} nachgearbeitet`, ton: "info", symbol: "rotate" },
    { text: `${zahl(z.offen)} offen`, ton: "warn", symbol: "circle-exclamation" },
  ];
}

/** Text des Auftrags unter Aufträge */
export function auftragstext(l: Laufeintrag): string {
  const kapitel = l.kapitel_gesamt ? `${zahl(l.kapitel_fertig)} von ${anzahl(l.kapitel_gesamt, "Kapitel", "Kapiteln")}` : "";
  if (l.stand === "laeuft") return [kapitel || "beginnt", l.fertig_gegen && kapitel ? `fertig ${gegen(l.fertig_gegen)}` : ""].filter(Boolean).join(", ");
  if (l.stand === "pause") return ["Pause", kapitel].filter(Boolean).join(", ");
  return ["Fehler", l.grund].filter(Boolean).join(": ");
}

/** Ergebnis eines Laufs, der nicht mehr in Arbeit ist */
export function ergebnistext(s: Laufstand): string {
  const z = s.zahlen;
  const kopf = s.stand === "fertig" ? "Fertig" : s.stand === "teilweise" ? "Abgebrochen, Fertiges bleibt" : "Fehler";
  return [kopf, `${zahl(z.uebersetzt)} von ${anzahl(z.bloecke, "Block", "Blöcken")} deutsch`, z.offen ? `${zahl(z.offen)} offen` : ""].filter(Boolean).join(", ");
}
