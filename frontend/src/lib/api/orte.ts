// Verbindungen, Orte und die Ablage eines Buchs
import { get } from "./client";
import type { Anschluesse } from "../stand/anschluesse.svelte";
import type { Ablage, BedeutungAntwort, Ort, Verbindung } from "../typen";

export const ladeVerbindungen = (): Promise<Verbindung[]> => get("/api/verbindungen");
export const ladeOrte = (): Promise<Ort[]> => get("/api/orte");
export const ladeAblage = (buch: number): Promise<Ablage> => get(`/api/books/${buch}/ablage`);
export const ladeOberflaeche = (): Promise<{ anschluesse?: Partial<Anschluesse> }> => get("/api/config/oberflaeche");

export const sucheBedeutung = (q: string, n = 20, buch?: number): Promise<BedeutungAntwort> => get("/api/suche/bedeutung", { q, n, buch });
