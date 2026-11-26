// Zeiten einer Übersetzung in Ortszeit und Dauer in Worten, ausgeschrieben: "fertig gegen 15:25", "1 Stunde 52 Minuten"
import { anzahl, zeitpunkt } from "../format";

const uhr = (d: Date) => d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
const tag = (d: Date) => Math.floor((d.getTime() - d.getTimezoneOffset() * 60_000) / 86_400_000);

/** Tage vom heutigen Tag aus, in Ortszeit: -1 gestern, 0 heute, 1 morgen */
function tageAb(d: Date, jetzt: Date): number {
  return tag(d) - tag(jetzt);
}

/** "15:25" heute, "morgen 03:10", "gestern 22:40", sonst "28.11., 03:10"; leer ohne Zeit */
export function zeitKurz(iso: string | null | undefined, jetzt = new Date()): string {
  const d = zeitpunkt(iso);
  if (!d) return "";
  const t = tageAb(d, jetzt);
  if (t === 0) return uhr(d);
  if (t === 1) return `morgen ${uhr(d)}`;
  if (t === -1) return `gestern ${uhr(d)}`;
  return `${d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}, ${uhr(d)}`;
}

/** "gegen 15:25", "morgen gegen 03:10", "am 28.11. gegen 03:10": für "fertig gegen ..." */
export function gegen(iso: string | null | undefined, jetzt = new Date()): string {
  const d = zeitpunkt(iso);
  if (!d) return "";
  const t = tageAb(d, jetzt);
  if (t <= 0) return `gegen ${uhr(d)}`;
  if (t === 1) return `morgen gegen ${uhr(d)}`;
  return `am ${d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} gegen ${uhr(d)}`;
}

function inWorten(minuten: number): string {
  const std = Math.floor(minuten / 60);
  const min = minuten % 60;
  if (!std) return anzahl(min, "Minute", "Minuten");
  return min ? `${anzahl(std, "Stunde", "Stunden")} ${anzahl(min, "Minute", "Minuten")}` : anzahl(std, "Stunde", "Stunden");
}

/** Gemessene Dauer: "unter 1 Minute", "12 Minuten", "1 Stunde 52 Minuten" */
export function dauer(sekunden: number): string {
  const minuten = Math.round(Math.max(0, sekunden) / 60);
  return minuten < 1 ? "unter 1 Minute" : inWorten(minuten);
}

/** Geschätzte Dauer ohne falsche Genauigkeit: ab einer Stunde auf zehn Minuten gerundet */
export function etwa(sekunden: number): string {
  const minuten = Math.round(Math.max(0, sekunden) / 60);
  if (minuten < 1) return "unter 1 Minute";
  return inWorten(minuten < 60 ? minuten : Math.round(minuten / 10) * 10);
}

/** Für Sätze: "etwa 3 Stunden", unter einer Minute ohne "etwa" */
export function ungefaehr(sekunden: number): string {
  const t = etwa(sekunden);
  return sekunden < 30 ? t : `etwa ${t}`;
}
