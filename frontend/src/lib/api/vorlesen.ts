// Vorlesen über den Server: Stimmen zur Wahl und der Ton als Strom
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
