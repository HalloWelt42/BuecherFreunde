// Die gebündelten Leseschriften als @font-face mit festen Adressen: die Kapitel eines EPUB liegen in eigenen Rahmen und
// sehen die Schriften der Seite nicht. Der lateinische Teil deckt Deutsch samt Umlauten ab.
import literata400 from "@fontsource/literata/files/literata-latin-400-normal.woff2?url";
import literata400kursiv from "@fontsource/literata/files/literata-latin-400-italic.woff2?url";
import literata700 from "@fontsource/literata/files/literata-latin-700-normal.woff2?url";
import atkinson400 from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-400-normal.woff2?url";
import atkinson400kursiv from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-400-italic.woff2?url";
import atkinson700 from "@fontsource/atkinson-hyperlegible/files/atkinson-hyperlegible-latin-700-normal.woff2?url";
import barlow400 from "@fontsource/barlow/files/barlow-latin-400-normal.woff2?url";
import barlow700 from "@fontsource/barlow/files/barlow-latin-700-normal.woff2?url";
import jetbrains400 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2?url";
import jetbrains700 from "@fontsource/jetbrains-mono/files/jetbrains-mono-latin-700-normal.woff2?url";

const SCHNITTE: [string, number, string, string][] = [
  ["Literata", 400, "normal", literata400], ["Literata", 400, "italic", literata400kursiv], ["Literata", 700, "normal", literata700],
  ["Atkinson Hyperlegible", 400, "normal", atkinson400], ["Atkinson Hyperlegible", 400, "italic", atkinson400kursiv], ["Atkinson Hyperlegible", 700, "normal", atkinson700],
  ["Barlow", 400, "normal", barlow400], ["Barlow", 700, "normal", barlow700],
  ["JetBrains Mono", 400, "normal", jetbrains400], ["JetBrains Mono", 700, "normal", jetbrains700],
];

export function leseschriftenCss(): string {
  return SCHNITTE.map(([familie, gewicht, stil, datei]) => `@font-face { font-family: "${familie}"; font-weight: ${gewicht}; font-style: ${stil}; font-display: swap; src: url("${new URL(datei, location.href).href}") format("woff2"); }`).join("\n");
}
