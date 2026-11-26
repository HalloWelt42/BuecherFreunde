// Schnittstelle der Annahme (Hochladen in Teilen)
import { anfrage, del, get, post, ApiError } from "./client";
import { AndererStand, OhneVerbindung, type AnnahmeDienst, type AnnahmeEintrag, type AnnahmeListe, type Annahmequelle, type NeueDatei } from "../annahme/typen";

/** Netzfehler und vorübergehende Antworten des Servers (5xx, 429) heißen: später noch einmal. */
async function mitVerbindung<T>(tun: () => Promise<T>): Promise<T> {
  try {
    return await tun();
  } catch (grund) {
    if (grund instanceof ApiError) {
      if (grund.status === 409 && typeof grund.data?.empfangen === "number") throw new AndererStand(grund.data.empfangen);
      if (grund.status === 0 || grund.status >= 500 || grund.status === 429) throw new OhneVerbindung(grund.message);
      throw grund;
    }
    if (grund instanceof DOMException && grund.name === "AbortError") throw grund;
    throw new OhneVerbindung(grund instanceof Error ? grund.message : "Keine Verbindung");
  }
}

export const annahmeDienst: AnnahmeDienst = {
  anlegen: (datei: NeueDatei) => mitVerbindung(() => post("/api/annahme", datei)),
  stand: (id: number) => mitVerbindung(() => get(`/api/annahme/${id}`)),
  teil: (id, ab, inhalt, abbruch) =>
    mitVerbindung(async () => {
      const antwort = await anfrage(`/api/annahme/${id}`, { method: "PATCH", body: inhalt, signal: abbruch, headers: { "Upload-Offset": String(ab), "Content-Type": "application/octet-stream" } });
      return (await antwort.json()) as AnnahmeEintrag;
    }),
};

export const ladeAnnahmen = (): Promise<AnnahmeListe> => get("/api/annahme");
export const annahmeErneut = (id: number): Promise<AnnahmeEintrag> => post(`/api/annahme/${id}/erneut`);
export const entferneAnnahme = (id: number): Promise<unknown> => del(`/api/annahme/${id}`);
export const blendeAnnahmenAus = (): Promise<unknown> => post("/api/annahme/ausblenden");
/** Viele auf einmal entfernen, nach Quelle und Stand; antwortet mit der neuen Liste */
export const raeumeAnnahmeAuf = (quelle: Annahmequelle, staende: readonly string[]): Promise<AnnahmeListe & { entfernt: number }> =>
  del(`/api/annahme?${new URLSearchParams([["quelle", quelle], ...staende.map((s) => ["stand", s])])}`);

export type Eingangsdatei = { name: string; groesse: number; stand: string; text: string; buch_id: number | null };
export type Eingangsordner = { bereit: boolean; ort: "kellerwolke" | "geraet"; pfad: string; dateien: Eingangsdatei[] };
export const ladeEingangsordner = (): Promise<Eingangsordner> => get("/api/annahme/eingangsordner");
export const nimmEingangsordnerAuf = (): Promise<{ neu: number }> => post("/api/annahme/eingangsordner");

/** Ereignisstrom; der Browser verbindet nach einem Abriss selbst neu. */
export function annahmeEreignisse(tun: (liste: AnnahmeListe) => void): () => void {
  const strom = new EventSource("/api/annahme/ereignisse");
  strom.onmessage = (e) => {
    try {
      tun(JSON.parse(e.data) as AnnahmeListe);
    } catch {
      // unvollständige Zeile: die nächste bringt den ganzen Stand
    }
  };
  return () => strom.close();
}
