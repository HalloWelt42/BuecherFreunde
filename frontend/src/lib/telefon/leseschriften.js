/**
 * Die gebündelten Leseschriften als @font-face-Regeln mit festen Adressen, für Dokumente, die die Schriften der Seite
 * nicht sehen (die Kapitel eines EPUB liegen in eigenen Rahmen). Der lateinische Teil deckt Deutsch samt Umlauten ab.
 */
import literata400 from "@fontsource/literata/files/literata-latin-400-normal.woff2?url";
import literata400kursiv from "@fontsource/literata/files/literata-latin-400-italic.woff2?url";
import literata700 from "@fontsource/literata/files/literata-latin-700-normal.woff2?url";
import atkinson400 from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-400-normal.woff2?url";
import atkinson400kursiv from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-400-italic.woff2?url";
import atkinson700 from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-700-normal.woff2?url";

const SCHNITTE = [
  ["Literata", 400, "normal", literata400],
  ["Literata", 400, "italic", literata400kursiv],
  ["Literata", 700, "normal", literata700],
  ["Atkinson Hyperlegible", 400, "normal", atkinson400],
  ["Atkinson Hyperlegible", 400, "italic", atkinson400kursiv],
  ["Atkinson Hyperlegible", 700, "normal", atkinson700],
];

/** @returns {string} CSS mit @font-face für alle Schnitte */
export function leseschriftenCss() {
  return SCHNITTE.map(([familie, gewicht, stil, datei]) => `@font-face {
  font-family: "${familie}"; font-weight: ${gewicht}; font-style: ${stil}; font-display: swap;
  src: url("${new URL(datei, location.href).href}") format("woff2");
}`).join("\n");
}
