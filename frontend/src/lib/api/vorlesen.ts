// Vorlesen über den Server: Stimmen zur Wahl, der Ton als Strom und je Buch die Stelle, an der es stehen blieb
import { anfrage, get } from "./client";

export interface Dienststimme {
  id: string;
  name: string;
  gruppe: "eigene" | "weitere" | "eingebaut";
}

export interface Dienststimmen {
  da: boolean;
  stimmen: Dienststimme[];
  hinweis: string;
}

export const ladeDienststimmen = (): Promise<Dienststimmen> => get("/api/vorlesen/stimmen");

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
