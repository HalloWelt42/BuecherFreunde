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

export function groesse(bytes: number | null | undefined): string {
  const b = bytes ?? 0;
  // Dezimal gezählt, wie am Server und im Dateimanager
  if (b < 1000) return `${zahl(b)} Byte`;
  const stufen = ["KB", "MB", "GB", "TB"];
  let wert = b / 1000;
  let stufe = 0;
  while (wert >= 1000 && stufe < stufen.length - 1) {
    wert /= 1000;
    stufe += 1;
  }
  const stellen = wert >= 100 || stufe === 0 ? 0 : 1;
  return `${wert.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen })} ${stufen[stufe]}`;
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

export function sprache(kuerzel: string | null | undefined): string {
  const k = (kuerzel ?? "").trim();
  return sprachen[k.slice(0, 2).toLowerCase()] && k.length <= 5 ? sprachen[k.slice(0, 2).toLowerCase()] : k;
}

export function formatName(format: string | null | undefined): string {
  return (format ?? "").replace(/^\./, "").toUpperCase();
}
