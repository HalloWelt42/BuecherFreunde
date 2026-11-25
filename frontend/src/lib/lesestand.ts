// Lesestand eines Buchs: eine Stelle liest alle Formen, die je gespeichert wurden (pdf:, epub:, txt:, page:, cfi:, percent:)
import { zahl } from "./format";
import type { Buch } from "./typen";

export interface Lesewerte {
  page?: number;
  zoom?: number;
  ansicht?: string;
  papier?: string;
  cfi?: string;
  percent?: number;
  fontSize?: number;
  fontFamily?: string;
  lineHeight?: number;
  fgColor?: string;
  bgColor?: string;
  maxWidthSingle?: number;
  maxWidthDouble?: number;
  singlePage?: boolean;
  randTransparent?: boolean;
  blattTransparent?: boolean;
  scrollPct?: number;
  breite?: number;
}

export interface Lesestand {
  angefangen: boolean;
  seite: number | null;
  /** 0 bis 1 */
  anteil: number;
}

const BREITEN = ["schmal", "mittel", "breit", "volle Breite"];
const ANSICHTEN: Record<string, string> = { scroll: "fortlaufend", breite: "Seitenbreite", seite: "ganze Seite", doppel: "Doppelseite", einzeln: "Einzelseite", text: "nur Text" };
const THEMEN: Record<string, string> = { "#ffffff": "Hell", "#f4ecd8": "Sepia", "#3d3526": "Dämmerung", "#1e1e1e": "Dunkel", "#0a0a0a": "Nacht" };

export function lesewerte(position: string | null | undefined): Lesewerte {
  const roh = position ?? "";
  const rest = roh.slice(roh.indexOf(":") + 1);
  if (/^(pdf|epub|txt):\{/.test(roh)) {
    try {
      return JSON.parse(rest) as Lesewerte;
    } catch {
      return {};
    }
  }
  if (roh.startsWith("txt:")) return { scrollPct: Number(rest) || 0 };
  if (roh.startsWith("cfi:")) return { cfi: rest };
  if (roh.startsWith("percent:")) return { percent: Number(rest) || 0 };
  const seite = roh.match(/page:(\d+)/);
  return seite ? { page: Number(seite[1]) } : {};
}

export function lesestand(buch: Pick<Buch, "reading_position" | "page_count">): Lesestand {
  const w = lesewerte(buch.reading_position);
  const seiten = buch.page_count || 0;
  let anteil = 0;
  if (w.page) anteil = seiten ? w.page / seiten : 0;
  else if (w.percent) anteil = w.percent / 100;
  else if (w.scrollPct) anteil = w.scrollPct / 100;
  anteil = Math.min(1, Math.max(0, anteil));
  return { angefangen: !!buch.reading_position && (anteil > 0 || !!w.cfi || !!w.page), seite: w.page ?? null, anteil };
}

/** "Seite 210 von 1.104" oder "62 % gelesen" */
export function standText(buch: Pick<Buch, "reading_position" | "page_count">): string {
  const s = lesestand(buch);
  if (!s.angefangen) return "";
  if (s.seite) return buch.page_count ? `Seite ${zahl(s.seite)} von ${zahl(buch.page_count)}` : `Seite ${zahl(s.seite)}`;
  return s.anteil > 0 ? `${Math.round(s.anteil * 100)} % gelesen` : "angefangen";
}

export function leseKnopf(buch: Pick<Buch, "reading_position" | "page_count">): string {
  const s = lesestand(buch);
  if (!s.angefangen) return "Lesen";
  if (s.seite) return `Weiterlesen, Seite ${zahl(s.seite)}`;
  return s.anteil > 0 ? `Weiterlesen, ${Math.round(s.anteil * 100)} %` : "Weiterlesen";
}

/** Wie zuletzt gelesen wurde, als kurze Angaben */
export function leseweise(position: string | null | undefined): string[] {
  const w = lesewerte(position);
  const teile: string[] = [];
  if (w.papier) teile.push(`Papier ${w.papier}`);
  if (w.ansicht) teile.push(ANSICHTEN[w.ansicht] ?? w.ansicht);
  if (w.zoom) teile.push(`Zoom ${Math.round(w.zoom)} %`);
  if (w.fontSize) teile.push(`Schrift ${w.fontSize} %`);
  if (w.fontFamily) teile.push(w.fontFamily.split(",")[0].replace(/'/g, "").trim());
  if (w.lineHeight) teile.push(`Zeilenabstand ${String(w.lineHeight).replace(".", ",")}`);
  if (w.singlePage !== undefined) teile.push(w.singlePage ? "einseitig" : "zweiseitig");
  if (w.maxWidthSingle && w.singlePage) teile.push(`Breite ${w.maxWidthSingle} px`);
  if (w.maxWidthDouble && w.singlePage === false) teile.push(`Breite ${w.maxWidthDouble} px`);
  if (w.breite !== undefined && w.breite >= 0) teile.push(BREITEN[w.breite] ?? "mittel");
  if (w.fgColor && w.bgColor) teile.push(`Thema ${THEMEN[w.bgColor] ?? "individuell"}`);
  return teile;
}

/** Schriftprobe in den zuletzt benutzten Farben; null ohne eigene Schrift */
export function schriftprobe(position: string | null | undefined): { schrift: string; name: string; farbe: string; grund: string } | null {
  const w = lesewerte(position);
  if (!w.fontFamily) return null;
  return { schrift: w.fontFamily, name: w.fontFamily.split(",")[0].replace(/'/g, "").trim(), farbe: w.fgColor ?? "", grund: w.bgColor ?? "" };
}

/** Adresse des Lesers an einer Stelle */
export function leseAdresse(id: number, stelle: Record<string, string | number | undefined> = {}): string {
  const p = new URLSearchParams();
  for (const [k, w] of Object.entries(stelle)) if (w !== undefined && w !== "") p.set(k, String(w));
  const q = p.toString();
  return `/book/${id}/read${q ? `?${q}` : ""}`;
}

/** Sprungziel einer Notiz oder Markierung: PDF nennt Seiten, EPUB eine Stelle im Buch, Text eine Prozentzahl */
export function stellenAdresse(id: number, format: string, stelle: { seite?: string | number | null; cfi?: string | null }): string {
  const seite = String(stelle.seite ?? "").trim();
  const cfi = String(stelle.cfi ?? "").trim();
  const alsSeite = cfi.match(/^page:(\d+)/)?.[1] ?? seite.match(/\d+/)?.[0];
  if (format === "pdf") return leseAdresse(id, { page: alsSeite });
  const prozent = cfi.match(/^(?:percent|pos|scroll):([\d.]+)/)?.[1] ?? seite.match(/([\d.,]+)\s*%/)?.[1]?.replace(",", ".");
  if (prozent) return leseAdresse(id, { percent: prozent });
  if (cfi.startsWith("epubcfi")) return leseAdresse(id, { cfi });
  if (seite.startsWith("epubcfi")) return leseAdresse(id, { cfi: seite });
  return leseAdresse(id, { page: alsSeite });
}
