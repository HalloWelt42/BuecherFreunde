// Katalog (BF-69): Bereiche und Kategorien, Entwurf, alte Regale aus Importen, Einordnen mit Vorschlägen.
// Schnittstelle nach docs/neubau/KATALOG.md.
import { del, download, get, patch, post, put } from "./client";
import type {
  Altfolgen, AltesRegal, Altziel, Entwurfsstand, Katalog, Katalogbereich, Katalogentwurf, Katalogfolgen, Kategorieregeln, Kategorietreffer,
  Katalogeinstellungen, Katalogweg, Laufstand, Vorschlagsseite,
} from "../typen";

const WEG = "/api/katalog";

export const ladeKatalog = (): Promise<Katalog> => get(WEG);
export const ladeStandard = (): Promise<Katalogentwurf> => get(`${WEG}/standard`);

// Entwurf
export const ladeEntwurf = (): Promise<Entwurfsstand> => get(`${WEG}/entwurf`);
/** "bestand" beginnt einen Lauf und antwortet mit ihm */
export const beginneEntwurf = (weg: Katalogweg): Promise<Entwurfsstand & { lauf?: Laufstand | null }> => post(`${WEG}/entwurf`, { weg });
export const speichereEntwurf = (entwurf: Katalogentwurf): Promise<Entwurfsstand> => put(`${WEG}/entwurf`, entwurf);
export const nimmEntwurfAn = (): Promise<Katalog> => post(`${WEG}/entwurf/annehmen`);
export const verwirfEntwurf = (): Promise<unknown> => del(`${WEG}/entwurf`);

// Als Datei sichern und laden
export const katalogDatei = (): Promise<Blob> => download(`${WEG}/datei`);
export const ladeKatalogDatei = (inhalt: unknown): Promise<Entwurfsstand> => post(`${WEG}/datei`, inhalt);

// Bereiche und Kategorien des gültigen Katalogs
export interface Bereichsangaben {
  name: string;
  zeichen: string;
  farbe: string;
  beschreibung: string;
  /** Arten des Werks: "" für Buch, sonst die Kennungen der Arten */
  arten: string[];
  verborgen: boolean;
}

export interface Kategorieangaben {
  bereich_id: number;
  name: string;
  zeichen: string;
  /** Leer: die Farbe des Bereichs */
  farbe: string;
  ki_beschreibung: string;
  regeln: Kategorieregeln;
  verborgen: boolean;
}

export type Ebene = "bereiche" | "kategorien";

export const legeBereichAn = (angaben: Bereichsangaben): Promise<Katalogbereich> => post(`${WEG}/bereiche`, angaben);
export const aendereBereich = (id: number, angaben: Partial<Bereichsangaben>): Promise<Katalogbereich> => patch(`${WEG}/bereiche/${id}`, angaben);
export const legeKategorieAn = (angaben: Kategorieangaben): Promise<unknown> => post(`${WEG}/kategorien`, angaben);
export const aendereKategorie = (id: number, angaben: Partial<Kategorieangaben>): Promise<unknown> => patch(`${WEG}/kategorien/${id}`, angaben);
export const loeschfolgen = (ebene: Ebene, id: number): Promise<Katalogfolgen> => get(`${WEG}/${ebene}/${id}/loeschfolgen`);
export const loesche = (ebene: Ebene, id: number): Promise<unknown> => del(`${WEG}/${ebene}/${id}`);
export const kategorietreffer = (id: number): Promise<Kategorietreffer> => get(`${WEG}/kategorien/${id}/treffer`);

// Regale aus Importen gehen im Katalog auf
export const ladeAlte = (): Promise<AltesRegal[]> => get(`${WEG}/alt`);
export const uebernimmAlte = (ids: number[], ziel: Altziel): Promise<{ buecher: number }> => post(`${WEG}/alt/uebernehmen`, { ids, ziel });
export const altfolgen = (id: number): Promise<Altfolgen> => get(`${WEG}/alt/${id}/loeschfolgen`);
export const entferneAltes = (id: number): Promise<unknown> => del(`${WEG}/alt/${id}`);

// Einordnen in Stapeln
export const beginneEinordnen = (stapel?: number): Promise<Laufstand> => post(`${WEG}/einordnen`, stapel ? { stapel } : {});
export const einordnenStand = (): Promise<Laufstand> => get(`${WEG}/einordnen/stand`);
export const pausiereEinordnen = (): Promise<Laufstand> => post(`${WEG}/einordnen/pause`);
export const setzeEinordnenFort = (): Promise<Laufstand> => post(`${WEG}/einordnen/fortsetzen`);

export const vorschlagsuebersicht = (): Promise<{ kategorie_id: number; anzahl: number }[]> => get(`${WEG}/vorschlaege/uebersicht`);
export const ladeVorschlaege = (kategorie: number, seite: number, proSeite: number): Promise<Vorschlagsseite> =>
  get(`${WEG}/vorschlaege`, { kategorie, seite, pro_seite: proSeite });
/** ids: diese; kategorie: alle offenen der Kategorie */
export const nimmVorschlaegeAn = (wahl: { ids: number[] } | { kategorie: number }): Promise<{ angenommen: number }> => post(`${WEG}/vorschlaege/annehmen`, wahl);
export const lehneVorschlaegeAb = (ids: number[]): Promise<{ abgelehnt: number }> => post(`${WEG}/vorschlaege/ablehnen`, { ids });

// Einstellungen des Einordnens und des Entwurfs
export const ladeKatalogeinstellungen = (): Promise<Katalogeinstellungen> => get(`${WEG}/einstellungen`);
export const speichereKatalogeinstellungen = (werte: Katalogeinstellungen): Promise<Katalogeinstellungen> => put(`${WEG}/einstellungen`, werte);
