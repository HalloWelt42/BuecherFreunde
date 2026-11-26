// Bücher übersetzen (BF-71): Fassungen, Lauf, Prüfbericht, Blöcke, Begriffsliste, Lesestand einer Übersetzung
import { anfrage, del, get, patch, post, put } from "./client";
import type {
  Anrede, Begriff, BegriffNeu, Bericht, Blockaktion, Blockantwort, Fassungseintrag, Fassungslesestand, Folgen, Laufeintrag, Laufstand, Zielsprache,
} from "../uebersetzung/typen";

export const holeFassungen = (buch: number): Promise<Fassungseintrag[]> => get(`/api/books/${buch}/fassungen`);
/** Welche Fassung "Lesen" öffnet; null: das Original */
export const waehleFassung = (buch: number, sprache: Zielsprache | null): Promise<Fassungseintrag[]> => put(`/api/books/${buch}/fassungen/wahl`, { sprache });
export const holeFolgen = (buch: number, sprache: Zielsprache): Promise<Folgen> => get(`/api/books/${buch}/fassungen/${sprache}/folgen`);
/** Startet oder setzt fort; die Anrede gilt für das ganze Buch */
export const starteUebersetzung = (buch: number, sprache: Zielsprache, anrede: Anrede = "du"): Promise<Laufstand> => post(`/api/books/${buch}/fassungen/${sprache}`, { anrede });

export const holeLaeufe = (): Promise<Laufeintrag[]> => get("/api/fassungen");
export const holeLaufstand = (fassung: number): Promise<Laufstand> => get(`/api/fassungen/${fassung}/stand`);
export const pausiereLauf = (fassung: number): Promise<Laufstand> => post(`/api/fassungen/${fassung}/pause`);
export const setzeLaufFort = (fassung: number): Promise<Laufstand> => post(`/api/fassungen/${fassung}/fortsetzen`);
export const brecheLaufAb = (fassung: number): Promise<Laufstand> => post(`/api/fassungen/${fassung}/abbrechen`);

export const holeBericht = (fassung: number): Promise<Bericht> => get(`/api/fassungen/${fassung}/bericht`);
/** "setzen" besteht die festen Prüfungen nicht: ApiError 422, die Befunde stehen in `data.befunde` */
export const aendereBlock = (fassung: number, kennung: string, aktion: Blockaktion): Promise<Blockantwort> =>
  post(`/api/fassungen/${fassung}/bloecke/${encodeURIComponent(kennung)}`, aktion);

export const holeBegriffe = (buch: number): Promise<Begriff[]> => get(`/api/books/${buch}/begriffe`);
export const legeBegriffAn = (buch: number, neu: BegriffNeu): Promise<Begriff> => post(`/api/books/${buch}/begriffe`, neu);
export const aendereBegriff = (id: number, aenderung: Partial<BegriffNeu>): Promise<Begriff> => patch(`/api/begriffe/${id}`, aenderung);
export const loescheBegriff = (id: number): Promise<{ geloescht: boolean; id: number }> => del(`/api/begriffe/${id}`);
/** Entfernt die genannten fragwürdigen Einträge eines Buchs; was nicht mehr fragwürdig ist, bleibt */
export const entferneFragwuerdige = (buch: number, ids: number[]): Promise<{ entfernt: number[] }> =>
  post(`/api/books/${buch}/begriffe/fragwuerdige/entfernen`, { ids });

/** Die Übersetzung als EPUB zum Lesen, auch teilweise */
export function fassungsdatei(fassung: number): string {
  return `/api/fassungen/${fassung}/datei`;
}

export const holeFassungslesestand = (fassung: number): Promise<Fassungslesestand> => get(`/api/fassungen/${fassung}/leseposition`);

/** keepalive: der Browser schickt auch dann zu Ende, wenn die Seite gerade verlassen wird */
export async function merkeFassungslesestand(fassung: number, position: string): Promise<void> {
  await anfrage(`/api/fassungen/${fassung}/leseposition`, { method: "PATCH", body: JSON.stringify({ position }), keepalive: true });
}
