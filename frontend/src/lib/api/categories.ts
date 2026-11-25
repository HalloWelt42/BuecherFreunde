// Regale (am Server: Kategorien)
import { del, get, patch, post } from "./client";
import type { Regal } from "../typen";

export const ladeKategorien = (): Promise<Regal[]> => get("/api/categories");
export const erstelleKategorie = (daten: Record<string, unknown>): Promise<Regal> => post("/api/categories", daten);
export const aktualisiereKategorie = (id: number, daten: Record<string, unknown>): Promise<Regal> => patch(`/api/categories/${id}`, daten);
export const loescheKategorie = (id: number): Promise<unknown> => del(`/api/categories/${id}`);
export const ordneBuchZu = (regal: number, buch: number): Promise<unknown> => post(`/api/categories/${regal}/books/${buch}`);
export const entferneBuch = (regal: number, buch: number): Promise<unknown> => del(`/api/categories/${regal}/books/${buch}`);
