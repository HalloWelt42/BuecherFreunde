// CSS für die Kapitelrahmen eines EPUB. Die Wahl im Leser soll über den Stilen des Buchs stehen, darum hier (und nur
// hier) !important.
import type { Leseart } from "../fluss/fluss";

export interface Epubdarstellung {
  groesse: number;
  schrift: string;
  zeilen: number;
  fg: string;
  bg: string;
  randTransparent: boolean;
  blattTransparent: boolean;
  einseitig: boolean;
}

export const randfarbe = (d: Epubdarstellung) => (d.randTransparent ? "transparent" : d.bg);
export const blattfarbe = (d: Epubdarstellung) => (d.blattTransparent ? "transparent" : d.bg);
/** Gescrollt steht immer nur eine Spalte */
export const einspaltig = (d: Epubdarstellung, art: Leseart) => d.einseitig || art === "scrollen";
/** Breite der Fläche: eine Spalte oder zwei nebeneinander, jede so breit wie das Blatt (lib/leser/leseraum.svelte.ts) */
export const breite = (d: Epubdarstellung, art: Leseart, spalte: number) => (einspaltig(d, art) ? spalte : 2 * spalte);

export function epubCss(d: Epubdarstellung, schriften: string): string {
  // Die gewählte Schrift gilt für allen Text, auch wo das Buch eigene Schriften setzt; Code bleibt, wie er ist
  const schrift = d.schrift ? `body, body *:not(pre):not(code):not(kbd):not(samp):not(pre *) { font-family: ${d.schrift} !important; }` : "";
  const ohneGrund = d.blattTransparent ? "div, section, article, main, aside, header, footer, nav, p { background-color: transparent !important; background-image: none !important; }" : "";
  const blatt = blattfarbe(d);
  return `${schriften}
html { --theme-bg-color: ${blatt}; }
html, body { color: ${d.fg} !important; background-color: ${blatt} !important; font-size: ${d.groesse}% !important; line-height: ${d.zeilen} !important; }
${schrift}
* { color: inherit !important; border-color: ${d.fg}33 !important; }
${ohneGrund}
a { color: ${d.fg} !important; text-decoration: underline !important; }
img, svg, video, canvas { max-width: 100% !important; height: auto !important; }
p, li, blockquote { hyphens: auto; -webkit-hyphens: auto; }`;
}

const KENNUNG = "bf-lesestil";

export function setzeStil(doc: Document, css: string, sprache: string): void {
  // Silbentrennung braucht die Sprache; fehlt sie im Kapitel, gilt die des Buchs
  if (!doc.documentElement.lang) doc.documentElement.lang = sprache || "de";
  let stil = doc.getElementById(KENNUNG);
  if (!stil) {
    stil = doc.createElement("style");
    stil.id = KENNUNG;
    doc.head.append(stil);
  }
  stil.textContent = css;
}
