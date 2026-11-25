// Gemerkte Werte im Browser. Ohne Speicher (privates Fenster, gesperrt, voll) gilt die Vorgabe, nie ein Fehler.

export function lies(schluessel: string, vorgabe = ""): string {
  try {
    return localStorage.getItem(schluessel) ?? vorgabe;
  } catch {
    return vorgabe;
  }
}

export function merke(schluessel: string, wert: string): void {
  try {
    localStorage.setItem(schluessel, wert);
  } catch {
    // ohne Speicher gilt der Wert nur für diese Seite
  }
}

export function vergiss(schluessel: string): void {
  try {
    localStorage.removeItem(schluessel);
  } catch {
    // nichts zu vergessen
  }
}

export function liesJson<T>(schluessel: string, vorgabe: T): T {
  const roh = lies(schluessel);
  if (!roh) return vorgabe;
  try {
    return JSON.parse(roh) as T;
  } catch {
    return vorgabe;
  }
}

export function merkeJson(schluessel: string, wert: unknown): void {
  merke(schluessel, JSON.stringify(wert));
}
