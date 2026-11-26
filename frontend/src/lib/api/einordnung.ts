// Die Art aller Werke bestimmen (BF-59, BF-77): Stand des Laufs, Fortsetzen nach einer Ablehnung der Leitstelle
import { get, post } from "./client";
import type { Einordnungsstand } from "../typen";

export const einordnungsstand = (): Promise<Einordnungsstand> => get("/api/einordnung/stand");
export const setzeEinordnungFort = (): Promise<Einordnungsstand> => post("/api/einordnung/fortsetzen");
