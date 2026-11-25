// Angaben aus Verzeichnissen und aus dem Buchtext
import { get, post } from "./client";

export const sucheMetadaten = (buch: number, quelle?: string): Promise<any> => post(`/api/metadata/buch/${buch}/anreichern${quelle ? `?quelle=${quelle}` : ""}`);
export const uebernehmMetadaten = (buch: number, daten: Record<string, unknown>): Promise<any> => post(`/api/metadata/buch/${buch}/uebernehmen`, daten);
export const ladeVolltext = (buch: number, von = 1, bis = 5): Promise<any> => get(`/api/metadata/buch/${buch}/volltext`, { seite_von: von, seite_bis: bis });
