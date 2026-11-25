// Die Leseschriften aller Leser an einer Stelle: lokal gebündelt (npm, OFL), nur der lateinische Teil, die Schnitte 400, 400 kursiv
// und 700. Geladen wird eine Schrift erst, wenn sie gewählt ist oder die Auswahl offen ist; die Startseite trägt nur die Adressen.
import literata400 from "@fontsource/literata/files/literata-latin-400-normal.woff2?url";
import literata400k from "@fontsource/literata/files/literata-latin-400-italic.woff2?url";
import literata700 from "@fontsource/literata/files/literata-latin-700-normal.woff2?url";
import sourceserif400 from "@fontsource/source-serif-4/files/source-serif-4-latin-400-normal.woff2?url";
import sourceserif400k from "@fontsource/source-serif-4/files/source-serif-4-latin-400-italic.woff2?url";
import sourceserif700 from "@fontsource/source-serif-4/files/source-serif-4-latin-700-normal.woff2?url";
import merriweather400 from "@fontsource/merriweather/files/merriweather-latin-400-normal.woff2?url";
import merriweather400k from "@fontsource/merriweather/files/merriweather-latin-400-italic.woff2?url";
import merriweather700 from "@fontsource/merriweather/files/merriweather-latin-700-normal.woff2?url";
import vollkorn400 from "@fontsource/vollkorn/files/vollkorn-latin-400-normal.woff2?url";
import vollkorn400k from "@fontsource/vollkorn/files/vollkorn-latin-400-italic.woff2?url";
import vollkorn700 from "@fontsource/vollkorn/files/vollkorn-latin-700-normal.woff2?url";
import barlow400 from "@fontsource/barlow/files/barlow-latin-400-normal.woff2?url";
import barlow700 from "@fontsource/barlow/files/barlow-latin-700-normal.woff2?url";
import jetbrains400 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2?url";
import jetbrains700 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-700-normal.woff2?url";
import atkinson400 from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-400-normal.woff2?url";
import atkinson400k from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-400-italic.woff2?url";
import atkinson700 from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-700-normal.woff2?url";
import lexend400 from "@fontsource/lexend/files/lexend-latin-400-normal.woff2?url";
import lexend700 from "@fontsource/lexend/files/lexend-latin-700-normal.woff2?url";
import andika400 from "@fontsource/andika/files/andika-latin-400-normal.woff2?url";
import andika400k from "@fontsource/andika/files/andika-latin-400-italic.woff2?url";
import andika700 from "@fontsource/andika/files/andika-latin-700-normal.woff2?url";
import opendyslexic400 from "@fontsource/opendyslexic/files/opendyslexic-latin-400-normal.woff2?url";
import opendyslexic400k from "@fontsource/opendyslexic/files/opendyslexic-latin-400-italic.woff2?url";
import opendyslexic700 from "@fontsource/opendyslexic/files/opendyslexic-latin-700-normal.woff2?url";

export type Schriftgruppe = "Mit Serifen" | "Ohne Serifen" | "Leichter lesen";
export const GRUPPEN: Schriftgruppe[] = ["Mit Serifen", "Ohne Serifen", "Leichter lesen"];

/** Gewicht, Stil, Adresse der Datei */
type Schnitt = [number, "normal" | "italic", string];

export interface Leseschrift {
  /** Kennung, unter der sie gemerkt wird */
  kennung: string;
  /** Name der Schrift, ein technischer Bezeichner */
  name: string;
  familie: string;
  gruppe: Schriftgruppe;
  /** Leer: die Schrift bringt das Gerät mit */
  schnitte: Schnitt[];
}

export const LESESCHRIFTEN: Leseschrift[] = [
  { kennung: "literata", name: "Literata", familie: '"Literata", Georgia, serif', gruppe: "Mit Serifen", schnitte: [[400, "normal", literata400], [400, "italic", literata400k], [700, "normal", literata700]] },
  { kennung: "source-serif", name: "Source Serif 4", familie: '"Source Serif 4", Georgia, serif', gruppe: "Mit Serifen", schnitte: [[400, "normal", sourceserif400], [400, "italic", sourceserif400k], [700, "normal", sourceserif700]] },
  { kennung: "merriweather", name: "Merriweather", familie: '"Merriweather", Georgia, serif', gruppe: "Mit Serifen", schnitte: [[400, "normal", merriweather400], [400, "italic", merriweather400k], [700, "normal", merriweather700]] },
  { kennung: "vollkorn", name: "Vollkorn", familie: '"Vollkorn", Georgia, serif', gruppe: "Mit Serifen", schnitte: [[400, "normal", vollkorn400], [400, "italic", vollkorn400k], [700, "normal", vollkorn700]] },
  { kennung: "georgia", name: "Georgia", familie: "Georgia, 'Times New Roman', serif", gruppe: "Mit Serifen", schnitte: [] },
  { kennung: "barlow", name: "Barlow", familie: 'Barlow, sans-serif', gruppe: "Ohne Serifen", schnitte: [[400, "normal", barlow400], [700, "normal", barlow700]] },
  { kennung: "system", name: "System", familie: 'system-ui, -apple-system, sans-serif', gruppe: "Ohne Serifen", schnitte: [] },
  { kennung: "jetbrains", name: "JetBrains Mono", familie: "'JetBrains Mono', monospace", gruppe: "Ohne Serifen", schnitte: [[400, "normal", jetbrains400], [700, "normal", jetbrains700]] },
  { kennung: "atkinson", name: "Atkinson Hyperlegible", familie: '"Atkinson Hyperlegible", system-ui, sans-serif', gruppe: "Leichter lesen", schnitte: [[400, "normal", atkinson400], [400, "italic", atkinson400k], [700, "normal", atkinson700]] },
  { kennung: "lexend", name: "Lexend", familie: '"Lexend", system-ui, sans-serif', gruppe: "Leichter lesen", schnitte: [[400, "normal", lexend400], [700, "normal", lexend700]] },
  { kennung: "andika", name: "Andika", familie: '"Andika", system-ui, sans-serif', gruppe: "Leichter lesen", schnitte: [[400, "normal", andika400], [400, "italic", andika400k], [700, "normal", andika700]] },
  { kennung: "opendyslexic", name: "OpenDyslexic", familie: '"OpenDyslexic", system-ui, sans-serif', gruppe: "Leichter lesen", schnitte: [[400, "normal", opendyslexic400], [400, "italic", opendyslexic400k], [700, "normal", opendyslexic700]] },
];

const erste = (familie: string) => familie.split(",")[0].replace(/["']/g, "").trim().toLowerCase();

/** Dieselbe Schrift, auch wenn eine frühere Fassung sie anders geschrieben hat */
export function gleicheSchrift(a: string, b: string): boolean {
  return erste(a) === erste(b);
}

export const schriftZu = (familie: string): Leseschrift | undefined => LESESCHRIFTEN.find((s) => gleicheSchrift(s.familie, familie));

const GELADEN = new WeakMap<Document, Set<string>>();

/** Meldet die Schnitte einer Schrift im Dokument an; der Browser holt sie, sobald Text sie braucht */
export function nutzeSchrift(familie: string, dok: Document = document): void {
  const s = schriftZu(familie);
  if (!s?.schnitte.length || typeof FontFace === "undefined") return;
  const da = GELADEN.get(dok) ?? new Set<string>();
  GELADEN.set(dok, da);
  if (da.has(s.kennung)) return;
  da.add(s.kennung);
  const Schrift = (dok.defaultView as (Window & typeof globalThis) | null)?.FontFace ?? FontFace;
  for (const [gewicht, stil, datei] of s.schnitte) {
    const f = new Schrift(s.name, `url("${new URL(datei, location.href).href}") format("woff2")`, { weight: String(gewicht), style: stil, display: "swap" });
    // Geholt wird erst, was der Text wirklich braucht: für die Probe nur der normale Schnitt
    dok.fonts.add(f);
  }
}

/** Alle, für die Proben in der Auswahl */
export function nutzeAlle(dok: Document = document): void {
  for (const s of LESESCHRIFTEN) nutzeSchrift(s.familie, dok);
}

/** @font-face für einen Kapitelrahmen (EPUB), der die Schriften der Seite nicht sieht; nur die gewählte */
export function schriftCss(familie: string): string {
  const s = schriftZu(familie);
  return (s?.schnitte ?? []).map(([gewicht, stil, datei]) => `@font-face { font-family: "${s!.name}"; font-weight: ${gewicht}; font-style: ${stil}; font-display: swap; src: url("${new URL(datei, location.href).href}") format("woff2"); }`).join("\n");
}
