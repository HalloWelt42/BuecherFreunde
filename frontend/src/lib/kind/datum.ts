// Zeitangaben für Kinder: kurz und ohne Zahlenkolonnen

/** Wann ein Buch zu Ende gelesen wurde: "heute", "gestern", "am Montag", "im Oktober", "im Oktober 2025" */
export function wannGelesen(iso: string | null, jetzt: Date): string {
  const d = iso ? new Date(iso.includes("T") || iso.endsWith("Z") ? iso : `${iso.replace(" ", "T")}Z`) : null;
  if (!d || Number.isNaN(d.getTime())) return "";
  const tag = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const tage = Math.round((tag(jetzt) - tag(d)) / 86_400_000);
  if (tage <= 0) return "heute";
  if (tage === 1) return "gestern";
  if (tage < 7) return `am ${d.toLocaleDateString("de-DE", { weekday: "long" })}`;
  const monat = d.toLocaleDateString("de-DE", { month: "long" });
  return d.getFullYear() === jetzt.getFullYear() ? `im ${monat}` : `im ${monat} ${d.getFullYear()}`;
}

/** Eine Dauer in Minuten: "25 Minuten", "1 Minute", "1 Stunde 10 Minuten" */
export function dauerText(minuten: number): string {
  const m = (n: number) => `${n} ${n === 1 ? "Minute" : "Minuten"}`;
  const stunden = Math.floor(minuten / 60);
  const rest = minuten % 60;
  if (!stunden) return m(minuten);
  return `${stunden} ${stunden === 1 ? "Stunde" : "Stunden"}${rest ? ` ${m(rest)}` : ""}`;
}

/** Restzeit: "noch 25 Minuten"; angefangene Minuten zählen mit */
export const nochZeit = (sekunden: number): string => `noch ${dauerText(Math.max(1, Math.ceil(sekunden / 60)))}`;
