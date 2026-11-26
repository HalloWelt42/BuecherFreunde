// Sammlungen, dazu die festen Listen der Arten und Gattungen
import { del, get, patch, post, put } from "./client";
import type { Art, Buch, Gattung, Sammlung, Sammlungseinstellungen, Sammlungsvorschlag, Vorschlagsstand } from "../typen";

export const ladeTypen = (): Promise<Art[]> => get("/api/collections/typen");
export const ladeGattungen = (): Promise<Gattung[]> => get("/api/collections/gattungen");

export const ladeSammlungen = (): Promise<Sammlung[]> => get("/api/collections");
export const holeSammlung = (id: number): Promise<Sammlung & { buecher?: Buch[] }> => get(`/api/collections/${id}`);
export const erstelleSammlung = (daten: Record<string, unknown>): Promise<Sammlung> => post("/api/collections", daten);
export const aktualisiereSammlung = (id: number, daten: Record<string, unknown>): Promise<Sammlung> => patch(`/api/collections/${id}`, daten);
export const loescheSammlung = (id: number): Promise<unknown> => del(`/api/collections/${id}`);
export const buchZuordnen = (sammlung: number, buch: number, band = ""): Promise<unknown> => post(`/api/collections/${sammlung}/buch/${buch}`, { band_nummer: band });
export const buchAusSammlung = (sammlung: number, buch: number): Promise<unknown> => del(`/api/collections/${sammlung}/buch/${buch}`);

/** Bandnummern 1 bis n in dieser Reihenfolge (BF-67) */
export const setzeReihenfolge = (sammlung: number, buecher: number[]): Promise<unknown> => put(`/api/collections/${sammlung}/reihenfolge`, { book_ids: buecher });

// Ab wie vielen Büchern eine Sammlung als ein Eintrag steht (BF-66)
export const ladeSammlungseinstellungen = (): Promise<Sammlungseinstellungen> => get("/api/collections/einstellungen");
export const speichereSammlungseinstellungen = (werte: Sammlungseinstellungen): Promise<Sammlungseinstellungen> => put("/api/collections/einstellungen", werte);

// Gefundene Reihen als Vorschläge (BF-66)
export const ladeVorschlaege = (): Promise<Sammlungsvorschlag[]> => get("/api/collections/vorschlaege");
export const sucheVorschlaege = (): Promise<unknown> => post("/api/collections/vorschlaege/suchen");
export const vorschlagsstand = (): Promise<Vorschlagsstand> => get("/api/collections/vorschlaege/stand");
/** Ohne Änderung so, wie gefunden; sonst mit eigenem Namen und nur den gewählten Büchern */
export const legeVorschlagAn = (id: number, aenderung?: { name: string; book_ids: number[] }): Promise<Sammlung> => post(`/api/collections/vorschlaege/${id}/anlegen`, aenderung);
export const verwirfVorschlag = (id: number): Promise<unknown> => post(`/api/collections/vorschlaege/${id}/verwerfen`);
