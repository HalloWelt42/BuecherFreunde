// Reine Regeln der Autorenseite: Lebensdaten, Sicherheit, Prüfung der Eingaben, Vergleich
import type { Autoreneinzeln, Autorvorschlag, Anreicherung } from "../../lib/api/authors";
import type { Vergleichszeile } from "../../lib/teile/Vergleichstabelle.svelte";

export function lebensdaten(a: { birth_year: number | null; death_year: number | null }): string {
  if (!a.birth_year && !a.death_year) return "";
  if (!a.death_year) return `geboren ${a.birth_year}`;
  return `${a.birth_year ?? "unbekannt"} bis ${a.death_year}`;
}

export function anfangsbuchstaben(name: string): string {
  return name.split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

/** Dunkle Schrift auf hellem Grund, helle auf dunklem */
export function schriftAuf(farbe: string): string {
  const [r, g, b] = [1, 3, 5].map((n) => Number.parseInt(farbe.slice(n, n + 2), 16));
  return r * 0.299 + g * 0.587 + b * 0.114 > 150 ? "#16221f" : "#ffffff";
}

export const SICHERHEIT: Record<string, { ton: "gut" | "warn" | "schlecht"; wort: string }> = {
  hoch: { ton: "gut", wort: "sicher" },
  mittel: { ton: "warn", wort: "wahrscheinlich" },
  niedrig: { ton: "schlecht", wort: "unsicher" },
};

export function sicherheit(stufe: string | undefined) {
  return SICHERHEIT[stufe ?? ""] ?? { ton: "warn" as const, wort: stufe ?? "" };
}

export const PUNKTE: [string, string][] = [
  ["10", "Beruf Schriftsteller oder Autor"], ["8", "Name stimmt genau"], ["5", "Deutscher Lexikonartikel"], ["1 bis 10", "Bekanntheit"], ["15", "Werke stimmen mit der Bibliothek überein"], ["30", "ISBN stimmt überein"],
];
export const STUFEN: [string, string][] = [["sicher", "ab 15 Punkten oder mit Buch- oder ISBN-Treffer"], ["wahrscheinlich", "8 bis 14 Punkte"], ["unsicher", "unter 8 Punkten"]];

export interface Autorformular {
  name: string;
  birth_year: string;
  death_year: string;
  nationality: string;
  website: string;
  biography: string;
}

export function formularVon(a: Autoreneinzeln): Autorformular {
  return { name: a.name ?? "", birth_year: a.birth_year ? String(a.birth_year) : "", death_year: a.death_year ? String(a.death_year) : "", nationality: a.nationality ?? "", website: a.website ?? "", biography: a.biography ?? "" };
}

/** Fehler je Feld, leer wenn alles stimmt. Der Server kennt nur Jahre, keine Tage. */
export function pruefe(f: Autorformular, jetzt = new Date().getFullYear()): Partial<Record<keyof Autorformular, string>> {
  const fehler: Partial<Record<keyof Autorformular, string>> = {};
  if (!f.name.trim()) fehler.name = "Der Name fehlt";
  for (const k of ["birth_year", "death_year"] as const) {
    const w = f[k].trim();
    if (w && !/^-?\d{1,4}$/.test(w)) fehler[k] = "Jahr als Zahl, etwa 1819";
    else if (w && Number(w) > jetzt) fehler[k] = "Dieses Jahr liegt in der Zukunft";
  }
  if (!fehler.birth_year && !fehler.death_year && f.birth_year.trim() && f.death_year.trim() && Number(f.death_year) < Number(f.birth_year)) fehler.death_year = "Vor dem Geburtsjahr";
  if (f.website.trim() && !/^https?:\/\/\S+\.\S+/i.test(f.website.trim())) fehler.website = "Ganze Adresse mit https://";
  return fehler;
}

/** Nur was sich geändert hat */
export function aenderungen(a: Autoreneinzeln, f: Autorformular): Record<string, unknown> {
  const vorher = formularVon(a);
  const daten: Record<string, unknown> = {};
  for (const k of Object.keys(vorher) as (keyof Autorformular)[]) {
    const neu = k === "biography" ? f[k] : f[k].trim();
    if (neu === vorher[k]) continue;
    daten[k] = k === "birth_year" || k === "death_year" ? (neu ? Number(neu) : null) : neu;
  }
  return daten;
}

const FELDER: [keyof Autorvorschlag & string, string][] = [
  ["name", "Name"], ["beschreibung", "Beschreibung"], ["birth_year", "Geburtsjahr"], ["death_year", "Todesjahr"], ["nationality", "Nationalität"], ["biography", "Biografie"], ["wikidata_id", "Wikidata"], ["wikipedia_url", "Wikipedia"],
];
const KURZ = 320;

function kurz(text: string): string {
  return text.length > KURZ ? `${text.slice(0, KURZ).trimEnd()} ...` : text;
}

/** Vorschlag neben Bestand. Fehlt dem Server ein Vergleichswert (Beschreibung), gilt der geladene Autor. */
export function vergleichszeilen(autor: Autoreneinzeln, a: Anreicherung, fotoAlt: string): Vergleichszeile[] {
  const zeilen: Vergleichszeile[] = [];
  for (const [k, feld] of FELDER) {
    const neu = String(a.vorschlag?.[k] ?? "");
    const alt = String(a.aktuell?.[k] ?? (autor as unknown as Record<string, unknown>)[k] ?? "");
    if (!neu && !alt) continue;
    const gleich = !neu || neu === alt;
    zeilen.push({ schluessel: k, feld, alt: kurz(alt), neu: kurz(neu || alt), gewaehlt: !gleich, gleich });
  }
  if (a.vorschlag?.photo_url) zeilen.push({ schluessel: "photo_url", feld: "Foto", alt: "", neu: "", gewaehlt: true, gleich: false, bildAlt: a.aktuell?.hat_foto ? fotoAlt : undefined, bildNeu: a.vorschlag.photo_url });
  return zeilen;
}

/** Was an den Server geht: nur gewählte Felder, dazu Werke und Herkunft des Vorschlags */
export function uebernahmefelder(v: Autorvorschlag, zeilen: Vergleichszeile[]): Record<string, unknown> {
  const felder: Record<string, unknown> = {};
  for (const z of zeilen) if (z.gewaehlt && !z.gleich) felder[z.schluessel] = v[z.schluessel as keyof Autorvorschlag];
  if (v.werke?.length) felder.werke = v.werke;
  for (const k of ["score", "konfidenz", "quelle"] as const) if (v[k]) felder[k] = v[k];
  return felder;
}

export function imBestand(titel: string, buecher: { title: string }[]): boolean {
  const t = titel.toLowerCase();
  return buecher.some((b) => b.title.toLowerCase().includes(t) || t.includes(b.title.toLowerCase()));
}
