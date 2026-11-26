// Begleitmaterial je Buch (BF-81, docs/neubau/SCHNITTSTELLE.md, Begleitmaterial). Hinzufügen läuft über die Annahme
// (lib/annahme, Ziel "material"); hier stehen Liste, Datei, Umbenennen, Folgen, Entfernen und die Funde des Abgleichs.
import { del, get, patch, post } from "./client";

export interface Material {
  id: string;
  buch_id: number;
  name: string;
  /** nach der Endung, etwa pdf, epub, text, markdown, bild, zip */
  art: string;
  /** zum Anzeigen, etwa PDF, Bild, Tabelle */
  art_name: string;
  /** Zeichen aus Font Awesome, ohne fa- */
  zeichen: string;
  groesse: number;
  ort: "kellerwolke" | "geraet";
  pfad: string;
  herkunft: "buchseite" | "hochladen" | "erkannt";
  /** öffnet in der App; sonst Herunterladen */
  oeffnen: boolean;
  /** sein Text kommt in die Suche */
  lesbar: boolean;
  text_stand: "offen" | "fertig" | "ohne" | "fehler";
  text_seiten: number;
  angelegt_am: string;
}

/** Eine Datei neben dem Original in der Kellerwolke, die nach dem Namen zum Buch gehört; erst ein Ja macht sie zu Material */
export interface Fund {
  knoten: string;
  buch_id: number;
  name: string;
  groesse: number;
  pfad: string;
  gefunden_am: string;
}

export interface Materialliste {
  material: Material[];
  funde: Fund[];
  /** wohin neues Material kommt */
  ort: "kellerwolke" | "geraet";
  groesse: number;
}

export interface Materialfolgen {
  id: string;
  name: string;
  buch_id: number;
  titel: string;
  ort: "kellerwolke" | "geraet";
  pfad: string;
  groesse: number;
  /** in den Papierkorb der Kellerwolke; sonst auf dem Gerät endgültig fort */
  papierkorb: boolean;
  /** sein Text steht in der Suche und fehlt danach */
  suche: boolean;
  seiten: number;
  stand: string;
}

const weg = (buch: number, mid = "") => `/api/books/${buch}/material${mid ? `/${encodeURIComponent(mid)}` : ""}`;

export const ladeMaterial = (buch: number): Promise<Materialliste> => get(weg(buch));
/** Umbenennen; die Endung bleibt, fehlt sie, kommt sie dazu */
export const benenneMaterialUm = (buch: number, mid: string, name: string): Promise<Material> => patch(weg(buch, mid), { name });
export const materialfolgen = (buch: number, mid: string): Promise<Materialfolgen> => get(`${weg(buch, mid)}/folgen`);
/** Nur mit dem Stand aus den Folgen; hat sich seither etwas geändert, 409 */
export const entferneMaterial = (buch: number, mid: string, stand: string): Promise<{ entfernt: boolean }> => del(`${weg(buch, mid)}?${new URLSearchParams({ stand })}`);
export const nimmFundAn = (buch: number, knoten: string): Promise<Material> => post(`${weg(buch)}/funde/${encodeURIComponent(knoten)}/annehmen`);
export const lehneFundAb = (buch: number, knoten: string): Promise<unknown> => post(`${weg(buch)}/funde/${encodeURIComponent(knoten)}/ablehnen`);

/** Die Datei zum Ansehen in der App; mit `herunterladen` als Anhang. Über das Inhalts-Cookie wie Buchdateien. */
export function materialDatei(buch: number, mid: string, herunterladen = false): string {
  return `${weg(buch, mid)}/datei${herunterladen ? "?herunterladen=true" : ""}`;
}
