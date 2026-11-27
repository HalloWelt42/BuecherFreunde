// Zahlen, Größen und Zeiten in deutscher Schreibweise

const zahlen = new Intl.NumberFormat("de-DE");

export function zahl(n: number | null | undefined): string {
  return zahlen.format(n ?? 0);
}

/** "12 von 340": was ein Filter von der ganzen Liste übrig lässt */
export function vonGesamt(teil: number, ganz: number): string {
  return `${zahl(teil)} von ${zahl(ganz)}`;
}

/** "1 Buch", "12 Bücher" */
export function anzahl(n: number, eins: string, viele: string): string {
  return `${zahl(n)} ${n === 1 ? eins : viele}`;
}

const STUFEN = ["KB", "MB", "GB", "TB"];

/** Die Einheit einer Größe, dezimal gezählt wie am Server und im Dateimanager, und wie viele Nachkommastellen sie zeigt */
function einheit(bytes: number): { teiler: number; name: string; stellen: number } {
  if (bytes < 1000) return { teiler: 1, name: "Byte", stellen: 0 };
  let teiler = 1000;
  let stufe = 0;
  while (bytes / teiler >= 1000 && stufe < STUFEN.length - 1) {
    teiler *= 1000;
    stufe += 1;
  }
  return { teiler, name: STUFEN[stufe], stellen: bytes / teiler >= 100 || stufe === 0 ? 0 : 1 };
}

const inEinheit = (bytes: number, e: ReturnType<typeof einheit>): string =>
  (bytes / e.teiler).toLocaleString("de-DE", { minimumFractionDigits: e.stellen, maximumFractionDigits: e.stellen });

export function groesse(bytes: number | null | undefined): string {
  const b = bytes ?? 0;
  const e = einheit(b);
  return `${inEinheit(b, e)} ${e.name}`;
}

/** "12,4 von 21,3 MB": der Teil in der Einheit des Ganzen */
export function groesseVon(teil: number, ganz: number): string {
  const e = einheit(ganz);
  return `${inEinheit(Math.min(teil, ganz), e)} von ${inEinheit(ganz, e)} ${e.name}`;
}

/** Wie lange etwas schon dauert: "0:23", "2:05", ab einer Stunde "1:02:03" */
export function dauer(sekunden: number): string {
  const s = Math.max(0, Math.floor(sekunden));
  const zwei = (n: number) => String(n).padStart(2, "0");
  return s >= 3600 ? `${Math.floor(s / 3600)}:${zwei(Math.floor(s / 60) % 60)}:${zwei(s % 60)}` : `${Math.floor(s / 60)}:${zwei(s % 60)}`;
}

/** Eine Wartezeit in Worten: "45 Sekunden", "2 Minuten" */
export function zeitspanne(sekunden: number): string {
  return sekunden < 60 ? anzahl(Math.round(sekunden), "Sekunde", "Sekunden") : anzahl(Math.round(sekunden / 60), "Minute", "Minuten");
}

/** Die Datenbank schreibt "2026-11-25 19:54:47" in Weltzeit, die neuen Wege schreiben mit Z. */
export function zeitpunkt(wert: string | null | undefined): Date | null {
  if (!wert) return null;
  const mitZone = /[zZ]|[+-]\d\d:?\d\d$/.test(wert);
  const d = new Date(mitZone ? wert : `${wert.replace(" ", "T")}${wert.length > 10 ? "Z" : ""}`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function datum(wert: string | null | undefined): string {
  return zeitpunkt(wert)?.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) ?? "";
}

export function datumZeit(wert: string | null | undefined): string {
  const d = zeitpunkt(wert);
  return d ? `${datum(wert)}, ${d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}` : "";
}

/** Seit wann etwas wartet: "seit heute 14:12", "seit gestern 9:05", "seit Montag, 24.11.", sonst "seit 24.11.2026" */
export function seitWann(wert: string | null | undefined, jetzt = new Date()): string {
  const d = zeitpunkt(wert);
  if (!d) return "";
  const tag = (x: Date) => Math.floor((x.getTime() - x.getTimezoneOffset() * 60_000) / 86_400_000);
  const tage = tag(jetzt) - tag(d);
  const uhr = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  if (tage <= 0) return `seit heute ${uhr}`;
  if (tage === 1) return `seit gestern ${uhr}`;
  if (tage < 7) return `seit ${d.toLocaleDateString("de-DE", { weekday: "long" })}, ${d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`;
  return `seit ${datum(wert)}`;
}

/** "heute", "gestern", "vor 3 Tagen", sonst das Datum */
export function tagWort(wert: string | null | undefined): string {
  const d = zeitpunkt(wert);
  if (!d) return "";
  const tag = (x: Date) => Math.floor((x.getTime() - x.getTimezoneOffset() * 60_000) / 86_400_000);
  const tage = tag(new Date()) - tag(d);
  if (tage <= 0) return "heute";
  if (tage === 1) return "gestern";
  return tage < 7 ? `vor ${tage} Tagen` : datum(wert);
}

const sprachen: Record<string, string> = { de: "Deutsch", en: "Englisch", fr: "Französisch", es: "Spanisch", it: "Italienisch", nl: "Niederländisch", la: "Latein", pt: "Portugiesisch", ru: "Russisch", pl: "Polnisch", sv: "Schwedisch", da: "Dänisch" };

/** Sprachen zur Wahl, mit Namen */
export const SPRACHEN: [string, string][] = Object.entries(sprachen);

export function sprache(kuerzel: string | null | undefined): string {
  const k = (kuerzel ?? "").trim();
  return sprachen[k.slice(0, 2).toLowerCase()] && k.length <= 5 ? sprachen[k.slice(0, 2).toLowerCase()] : k;
}

export function formatName(format: string | null | undefined): string {
  return (format ?? "").replace(/^\./, "").toUpperCase();
}
