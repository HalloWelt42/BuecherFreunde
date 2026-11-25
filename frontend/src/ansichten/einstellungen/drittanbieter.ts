// Verwendete Pakete und ihre Lizenzen

export interface Paket {
  name: string;
  lizenz: string;
  adresse: string;
  zweck: string;
}

const p = (name: string, lizenz: string, adresse: string, zweck: string): Paket => ({ name, lizenz, adresse, zweck });

export const server: Paket[] = [
  p("FastAPI", "MIT", "https://github.com/tiangolo/fastapi", "Schnittstelle des Servers"),
  p("Uvicorn", "BSD-3-Clause", "https://github.com/encode/uvicorn", "Dienst, der Anfragen annimmt"),
  p("PyMuPDF", "AGPL-3.0", "https://github.com/pymupdf/PyMuPDF", "PDF: Text, Umschlag, Angaben"),
  p("EbookLib", "AGPL-3.0", "https://github.com/aerkalov/ebooklib", "EPUB lesen"),
  p("mobi", "GPL-3.0", "https://github.com/iscc/mobi", "MOBI lesen"),
  p("Pillow", "MIT-CMU", "https://github.com/python-pillow/Pillow", "Bilder der Umschläge"),
  p("httpx", "BSD-3-Clause", "https://github.com/encode/httpx", "Verbindung zu Kellerwolke und Hausdiensten"),
  p("Requests", "Apache-2.0", "https://github.com/psf/requests", "Abruf von Angaben und freien Büchern"),
  p("aiosqlite", "MIT", "https://github.com/omnilib/aiosqlite", "Datenbank"),
  p("openai", "Apache-2.0", "https://github.com/openai/openai-python", "Anschluss an die KI"),
  p("Pydantic Settings", "MIT", "https://github.com/pydantic/pydantic-settings", "Einrichtung"),
  p("BeautifulSoup4", "MIT", "https://www.crummy.com/software/BeautifulSoup/", "Text aus Webseiten"),
  p("isbnlib", "LGPL-3.0", "https://github.com/xlcnd/isbnlib", "ISBN prüfen und suchen"),
  p("python-multipart", "Apache-2.0", "https://github.com/andrew-d/python-multipart", "Hochladen"),
];

export const oberflaeche: Paket[] = [
  p("Svelte 5", "MIT", "https://github.com/sveltejs/svelte", "Oberfläche"),
  p("Vite", "MIT", "https://github.com/vitejs/vite", "Bau der Oberfläche"),
  p("pdfjs-dist", "Apache-2.0", "https://github.com/mozilla/pdf.js", "PDF im Browser zeigen"),
  p("foliate-js", "MIT", "https://github.com/johnfactotum/foliate-js", "EPUB und MOBI lesen"),
  p("svelte-markdown", "MIT", "https://github.com/humanspeak/svelte-markdown", "Markdown zeigen"),
  p("highlight.js", "BSD-3-Clause", "https://github.com/highlightjs/highlight.js", "Farben in Quelltext"),
  p("Mermaid", "MIT", "https://github.com/mermaid-js/mermaid", "Diagramme in Markdown"),
  p("hash-wasm", "MIT", "https://github.com/Daninet/hash-wasm", "Prüfsumme beim Hochladen"),
  p("Font Awesome Free", "MIT / CC BY 4.0", "https://github.com/FortAwesome/Font-Awesome", "Zeichen"),
  p("Barlow", "OFL-1.1", "https://github.com/jpt/barlow", "Schrift der Oberfläche"),
  p("Literata", "OFL-1.1", "https://github.com/googlefonts/literata", "Schrift der Bücher"),
  p("Atkinson Hyperlegible", "OFL-1.1", "https://github.com/googlefonts/atkinson-hyperlegible", "Leseschrift"),
  p("Source Serif 4", "OFL-1.1", "https://github.com/adobe-fonts/source-serif", "Leseschrift"),
  p("Merriweather", "OFL-1.1", "https://github.com/SorkinType/Merriweather", "Leseschrift"),
  p("Vollkorn", "OFL-1.1", "https://github.com/FAlthausen/Vollkorn-Typeface", "Leseschrift"),
  p("Lexend", "OFL-1.1", "https://github.com/googlefonts/lexend", "Leseschrift für leichteres Lesen"),
  p("Andika", "OFL-1.1", "https://github.com/silnrsi/font-andika", "Leseschrift für leichteres Lesen"),
  p("OpenDyslexic", "OFL-1.1", "https://github.com/antijingoist/opendyslexic", "Leseschrift für leichteres Lesen"),
  p("JetBrains Mono", "OFL-1.1", "https://github.com/JetBrains/JetBrainsMono", "Schrift für Quelltext"),
];

export type Strenge = "gut" | "warn" | "schlecht";

/** gut: frei nutzbar, warn: schwaches, schlecht: starkes Copyleft */
export function strenge(lizenz: string): Strenge {
  if (lizenz.startsWith("LGPL")) return "warn";
  return /^A?GPL/.test(lizenz) ? "schlecht" : "gut";
}
