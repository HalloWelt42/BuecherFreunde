// Einlesen von Ordnern und Ergänzen der Bibliothek
import { del, get, post } from "./client";

export type Ergaenzungsart = "cover" | "isbn" | "metadaten" | "volltext";

export const scanneImportVerzeichnis = (anreichern = false): Promise<any> => post(`/api/import/scan?anreichern=${anreichern}`);
export const scanneExternesVerzeichnis = (anreichern = false): Promise<any> => post(`/api/import/externes-verzeichnis?anreichern=${anreichern}`);
export const einlesenVorschau = (quelle: "import" | "extern"): Promise<any> => get("/api/import/vorschau", { verzeichnis: quelle });
export const bereinigeImportTasks = (): Promise<any> => del("/api/import/bereinigen");
export const brecheImportAb = (): Promise<any> => post("/api/import/abbrechen");

function abfrage(typen: string[], kategorie: number | null, manuell: boolean): string {
  const p = new URLSearchParams({ typen: typen.join(","), manuell_einschliessen: String(manuell) });
  if (kategorie !== null) p.set("kategorie", String(kategorie));
  return p.toString();
}

export const starteRescan = (typen: string[], kategorie: number | null = null, manuell = false): Promise<any> => post(`/api/books/rescan?${abfrage(typen, kategorie, manuell)}`);
export const rescanVorschau = (typen: string[], kategorie: number | null = null, manuell = false): Promise<any> => get(`/api/books/rescan/vorschau?${abfrage(typen, kategorie, manuell)}`);
export const rescanKategorien = (typen: string[], manuell = false): Promise<any> => get(`/api/books/rescan/kategorien?${abfrage(typen, null, manuell)}`);
export const holeRescanStatus = (): Promise<any> => get("/api/books/rescan/status");
export const brecheRescanAb = (): Promise<any> => post("/api/books/rescan/abbrechen");
