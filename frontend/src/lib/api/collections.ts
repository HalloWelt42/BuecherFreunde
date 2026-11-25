// Sammlungen
import { del, get, patch, post } from "./client";
import type { Buch, Sammlung } from "../typen";

export const ladeSammlungen = (): Promise<Sammlung[]> => get("/api/collections");
export const holeSammlung = (id: number): Promise<Sammlung & { buecher?: Buch[] }> => get(`/api/collections/${id}`);
export const erstelleSammlung = (daten: Record<string, unknown>): Promise<Sammlung> => post("/api/collections", daten);
export const aktualisiereSammlung = (id: number, daten: Record<string, unknown>): Promise<Sammlung> => patch(`/api/collections/${id}`, daten);
export const loescheSammlung = (id: number): Promise<unknown> => del(`/api/collections/${id}`);
export const buchZuordnen = (sammlung: number, buch: number, band = ""): Promise<unknown> => post(`/api/collections/${sammlung}/buch/${buch}`, { band_nummer: band });
export const buchAusSammlung = (sammlung: number, buch: number): Promise<unknown> => del(`/api/collections/${sammlung}/buch/${buch}`);
