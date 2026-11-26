// Schnittstelle der Annahme (Hochladen in Teilen, Vorschau vor dem Übernehmen, BF-80)
import { anfrage, del, get, patch, post, put, ApiError } from "./client";
import { AndererStand, OhneVerbindung, type AnnahmeDienst, type AnnahmeEintrag, type AnnahmeListe, type Annahmequelle, type NeueDatei, type Vorschaukurz } from "../annahme/typen";
import type { Felderaenderung, Hinzufuegeeinstellungen, Verwerffolgen, Vorgabe, Vorschau } from "../annahme/vorschautypen";

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

/** Eine Datei anmelden: in eine Vorschau (ohne genannte bekommt jede ihre eigene) oder als Begleitmaterial eines Buchs */
function anmelden({ name, groesse, sha256, ziel }: NeueDatei): Promise<AnnahmeEintrag> {
  if (ziel.art === "material") return post(`/api/books/${ziel.buch}/material`, { name, groesse, sha256, entpacken: ziel.entpacken });
  return post("/api/annahme", { name, groesse, sha256, anreichern: ziel.anreichern, ...(ziel.vorschau ? { vorschau: ziel.vorschau } : {}) });
}

export const annahmeDienst: AnnahmeDienst = {
  anlegen: (datei: NeueDatei) => mitVerbindung(() => anmelden(datei)),
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

// Vorschau vor dem Übernehmen (BF-80)

const vorschauweg = (id: string) => `/api/annahme/vorschau/${encodeURIComponent(id)}`;

export const ladeVorschauen = (): Promise<Vorschaukurz[]> => get("/api/annahme/vorschau");
/** Eine leere Vorschau für mehrere Dateien; die Dateien nennen sie beim Anmelden */
export const legeVorschauAn = (name: string, vorgabe?: Partial<Vorgabe>): Promise<Vorschau> => post("/api/annahme/vorschau", { name, ...(vorgabe ? { vorgabe } : {}) });
export const ladeVorschau = (id: string): Promise<Vorschau> => get(vorschauweg(id));
/** Felder einer oder mehrerer Dateien; geht eine nicht, ändert sich keine (422 mit Feld und Grund) */
export const aendereVorschau = (id: string, ids: number[], felder: Felderaenderung): Promise<Vorschau> => patch(vorschauweg(id), { ids, felder });
/** Ohne ids alle wartenden */
export const uebernimmVorschau = (id: string, ids?: number[]): Promise<{ weiter: number; vorschau: Vorschau }> => post(`${vorschauweg(id)}/uebernehmen`, ids ? { ids } : {});
export const verwerffolgen = (id: string): Promise<Verwerffolgen> => get(`${vorschauweg(id)}/folgen`);
/** Nur mit dem Stand aus den Folgen; hat sich seither etwas geändert, 409 */
export const verwirfVorschau = (id: string, stand: string): Promise<{ verworfen: number; vorschau: Vorschau }> => del(`${vorschauweg(id)}?${new URLSearchParams({ stand })}`);
/** Der Umschlag, den das Lesen fand, über das Inhalts-Cookie */
export const aufnahmeUmschlag = (id: number): string => `/api/annahme/${id}/umschlag`;

export const ladeHinzufuegeeinstellungen = (): Promise<Hinzufuegeeinstellungen> => get("/api/annahme/einstellungen");
export const speichereHinzufuegeeinstellungen = (werte: Hinzufuegeeinstellungen): Promise<Hinzufuegeeinstellungen> => put("/api/annahme/einstellungen", werte);

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
