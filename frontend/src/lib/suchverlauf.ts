// Suchverlauf im Speicher des Browsers
import { liesJson, merkeJson } from "./speicher";

const SCHLUESSEL = "search_history";
const HOECHSTENS = 50;
const AB_ZEICHEN = 2;

export function ladeVerlauf(): string[] {
  const verlauf = liesJson<unknown>(SCHLUESSEL, []);
  return Array.isArray(verlauf) ? verlauf.filter((b): b is string => typeof b === "string") : [];
}

/** Begriff vorn einreihen, ohne Doppel */
export function merkeBegriff(verlauf: string[], begriff: string): string[] {
  const sauber = begriff.trim();
  if (sauber.length < AB_ZEICHEN) return verlauf;
  const neu = [sauber, ...verlauf.filter((b) => b !== sauber)].slice(0, HOECHSTENS);
  merkeJson(SCHLUESSEL, neu);
  return neu;
}

export function vergissBegriff(verlauf: string[], begriff: string): string[] {
  const neu = verlauf.filter((b) => b !== begriff);
  merkeJson(SCHLUESSEL, neu);
  return neu;
}

export function leereVerlauf(): string[] {
  merkeJson(SCHLUESSEL, []);
  return [];
}
