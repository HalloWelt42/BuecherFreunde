// Grundeinstellungen, Fassung, Zustand
import { get, post } from "./client";

export const ladeConfig = (): Promise<any> => get("/api/config");
export const ladeVersion = (): Promise<{ version: string }> => get("/api/config/version");
export const ladePfade = (): Promise<Record<string, string>> => get("/api/config/paths");
export const healthCheck = (): Promise<{ status: string }> => get("/api/health");
export const gutenbergStatus = (): Promise<any> => get("/api/gutenberg/status");
export const sicherungAnlegen = (): Promise<any> => post("/api/backup/create");
export const sicherungen = (): Promise<any> => get("/api/backup/list");
