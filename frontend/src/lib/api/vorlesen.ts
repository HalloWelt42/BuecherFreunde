// Vorlesen über den Server und die Vertonung (BF-14): Stimmen zur Wahl mit ihren Bereichen, der Ton als Strom und je Buch die
// Stelle, an der es stehen blieb
import { anfrage, get, post } from "./client";

/** Wo eine Stimme der Vertonung herkommt: freigegebene private, fremde Klonstimmen, ihr Katalog */
export type Stimmbereich = "privat" | "fremd" | "katalog";

export interface Dienststimme {
  /** Wie die Vertonung sie schreibt: "katalog:<name>" oder die Kennung einer Klonstimme */
  id: string;
  name: string;
  bereich: Stimmbereich;
  /** Sprache der Probe einer Klonstimme */
  sprache: string | null;
}

export interface Bereichsstand {
  bereich: Stimmbereich;
  /** Gibt die Vertonung diesen Bereich BücherFreunde frei? */
  frei: boolean;
  /** Gesperrt: Grund und Weg zur Freigabe */
  hinweis: string;
}

export interface Dienststimmen {
  da: boolean;
  stimmen: Dienststimme[];
  bereiche: Bereichsstand[];
  hinweis: string;
}

/** Die Bereiche als Gruppen der Stimmenwahl, in der Folge der Vertonung */
export const BEREICHSNAMEN: Record<Stimmbereich, string> = { privat: "Private Stimmen", fremd: "Fremde Stimmen", katalog: "Eingebaute Stimmen" };

/** Die Stimmen gruppiert nach Bereich, als [Gruppe, [Wert, Name]]; `wert` macht aus der Kennung den Wert der Auswahl */
export function stimmgruppen(d: Dienststimmen | null, wert: (id: string) => string = (id) => id): [string, [string, string][]][] {
  const aus: [string, [string, string][]][] = [];
  for (const bereich of Object.keys(BEREICHSNAMEN) as Stimmbereich[]) {
    const liste = (d?.stimmen ?? []).filter((s) => s.bereich === bereich).map((s): [string, string] => [wert(s.id), s.name]);
    if (liste.length) aus.push([BEREICHSNAMEN[bereich], liste]);
  }
  return aus;
}

/** Warum private Stimmen fehlen und wo man sie freigibt; leer, wenn sie frei sind */
export const freigabeHinweis = (d: Dienststimmen | null): string => d?.bereiche.find((b) => !b.frei)?.hinweis ?? "";

export const ladeDienststimmen = (): Promise<Dienststimmen> => get("/api/vorlesen/stimmen");

/** Eine Stimmprobe: Text und Adresse des abgelegten Tons */
export interface Probenton {
  text: string;
  /** leer: die Stimme des Geräts spricht den Text */
  url: string | null;
}

/** Die Probe einer Stimme mit den Werten des Profils, meist vorab gesprochen (BF-114); eine Stimme des Geräts bekommt nur den Text */
export const holeStimmprobe = (stimme: string): Promise<Probenton> => post("/api/vorlesen/probe", { stimme });

export function vorleseStrom(text: string, stimme: string, abbruch: AbortSignal): Promise<Response> {
  return anfrage("/api/vorlesen", { method: "POST", body: JSON.stringify({ text, stimme }), signal: abbruch });
}

/** Wo das Vorlesen eines Buchs stehen blieb (BF-37): Einheit der Lesequelle und Anfang des Satzes; bis: Ende des Umfangs */
export interface VorlesestelleNeu {
  einheit: number;
  zeichen: number;
  bis_einheit: number | null;
  bis_zeichen: number | null;
  /** Was gewählt war, etwa "Dieses Kapitel" */
  umfang: string;
  /** Wie die Stelle heißt, etwa "Seite 12" */
  ort: string;
}

export interface Vorlesestelle extends VorlesestelleNeu {
  gemerkt_am: string;
}

export const holeVorlesestelle = (buch: number): Promise<Vorlesestelle | null> => get(`/api/books/${buch}/vorlesestelle`);

/** keepalive: geht auch noch hinaus, wenn das Fenster gerade zugeht */
export async function merkeVorlesestelle(buch: number, stelle: VorlesestelleNeu): Promise<Vorlesestelle> {
  return (await anfrage(`/api/books/${buch}/vorlesestelle`, { method: "PUT", body: JSON.stringify(stelle), keepalive: true })).json();
}

export async function vergissVorlesestelle(buch: number): Promise<void> {
  await anfrage(`/api/books/${buch}/vorlesestelle`, { method: "DELETE" });
}
