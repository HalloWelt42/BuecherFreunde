// Vorschlag eines Verzeichnisses gegen die Angaben des Buchs: welche Felder sich unterscheiden und was gesendet wird
import type { Vergleichszeile } from "../../lib/teile/Vergleichstabelle.svelte";

export type Quelle = "google_books" | "open_library" | "wikipedia";

export interface Vorschlag {
  titel?: string;
  autor?: string;
  verlag?: string;
  jahr?: number | string | null;
  seiten?: number | string | null;
  isbn?: string;
  sprache?: string;
  beschreibung?: string;
  cover_url?: string;
  kategorien?: string[];
  raw?: Record<string, unknown>;
}

export interface Aktuell extends Vorschlag {
  hat_cover?: boolean;
}

export const felder: [keyof Vorschlag & string, string][] = [["titel", "Titel"], ["autor", "Autor"], ["verlag", "Verlag"], ["jahr", "Jahr"], ["seiten", "Seiten"], ["isbn", "ISBN"], ["sprache", "Sprache"], ["beschreibung", "Beschreibung"]];

const text = (w: unknown) => (w === null || w === undefined ? "" : String(w));

export function vergleiche(vorschlag: Vorschlag, aktuell: Aktuell, umschlag: string): Vergleichszeile[] {
  const zeilen: Vergleichszeile[] = [];
  for (const [schluessel, feld] of felder) {
    const alt = text(aktuell[schluessel]);
    const neu = text(vorschlag[schluessel]);
    if (!alt && !neu) continue;
    const gleich = !neu || neu === alt;
    zeilen.push({ schluessel, feld, alt, neu: neu || alt, gewaehlt: !gleich, gleich });
  }
  if (vorschlag.cover_url) zeilen.push({ schluessel: "cover", feld: "Umschlag", alt: "", neu: "", gewaehlt: true, gleich: false, bildAlt: aktuell.hat_cover ? umschlag : undefined, bildNeu: vorschlag.cover_url });
  if (vorschlag.kategorien?.length) {
    const schon = new Set(aktuell.kategorien ?? []);
    const dazu = vorschlag.kategorien.filter((k) => !schon.has(k));
    zeilen.push({ schluessel: "kategorien", feld: "Regale", alt: (aktuell.kategorien ?? []).join(", "), neu: dazu.length ? `dazu: ${dazu.join(", ")}` : "alle schon da", gewaehlt: dazu.length > 0, gleich: dazu.length === 0 });
  }
  return zeilen;
}

/** Nur Gewähltes geht an den Server; Listen aus "Alle Daten" kommen als Regale dazu */
export function nutzlast(vorschlag: Vorschlag, quelle: string, gewaehlt: Set<string>, listen: Set<string>): Record<string, unknown> {
  const daten: Record<string, unknown> = {};
  for (const [schluessel] of felder) if (gewaehlt.has(schluessel)) daten[schluessel] = vorschlag[schluessel];
  if (gewaehlt.has("cover") && vorschlag.cover_url) {
    daten.cover_url = vorschlag.cover_url;
    daten.quelle = quelle;
  }
  const regale = new Set<string>(gewaehlt.has("kategorien") ? vorschlag.kategorien : []);
  for (const name of listen) for (const wert of alsListe(vorschlag.raw?.[name])) regale.add(wert);
  if (regale.size) daten.kategorien = [...regale];
  return daten;
}

/** Eine Liste aus lauter Texten, sonst leer */
export function alsListe(wert: unknown): string[] {
  return Array.isArray(wert) && wert.length > 0 && wert.every((w) => typeof w === "string") ? (wert as string[]).filter(Boolean) : [];
}
