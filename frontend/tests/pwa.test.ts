// BF-20: App am iPhone: Vorrat des Dienstes im Hintergrund, Statusleiste, Startbilder, Ohne Netz lesen
import { vorratAus } from "../vite.config.js";
import { sprich } from "../src/lib/hintergrund";
import { darstellung } from "../src/lib/stand/darstellung.svelte";

const dateien = import.meta.glob<string>(["../index.html", "../public/sw.js"], { query: "?raw", import: "default", eager: true });
const datei = (name: string): string => Object.entries(dateien).find(([p]) => p.endsWith(name))?.[1] ?? "";
const startbilder = Object.keys(import.meta.glob("../public/startbild-*.png", { query: "?url", import: "default", eager: true })).map((p) => p.replace("../public", ""));

/** Ein Bau wie von Rollup: Einstieg, Leser in Formaten, Diagramme */
function teil(fileName: string, ueber: Record<string, unknown> = {}) {
  return { type: "chunk", fileName, isEntry: false, imports: [], dynamicImports: [], moduleIds: [], viteMetadata: { importedCss: new Set(), importedAssets: new Set() }, ...ueber };
}

describe("Vorrat des Dienstes im Hintergrund", () => {
  const bau = Object.fromEntries([
    teil("assets/index.js", { isEntry: true, imports: ["assets/geteilt.js"], dynamicImports: ["assets/PdfLeser.js", "assets/Danke.js"], moduleIds: ["/x/src/main.ts"], viteMetadata: { importedCss: new Set(["assets/index.css"]), importedAssets: new Set(["assets/barlow.woff2"]) } }),
    teil("assets/geteilt.js"),
    teil("assets/PdfLeser.js", { moduleIds: ["/x/src/ansichten/leser/PdfLeser.svelte"], dynamicImports: ["assets/pdf.js", "assets/Markdown.js"] }),
    teil("assets/pdf.js", { moduleIds: ["/x/node_modules/pdfjs-dist/legacy/build/pdf.mjs"], viteMetadata: { importedCss: new Set(), importedAssets: new Set(["assets/pdf.worker.min.mjs"]) } }),
    teil("assets/Markdown.js", { moduleIds: ["/x/src/ansichten/leser/Markdown.svelte"], dynamicImports: ["assets/mermaid.js"] }),
    teil("assets/mermaid.js", { moduleIds: ["/x/node_modules/mermaid/dist/mermaid.core.mjs"] }),
    teil("assets/Danke.js", { moduleIds: ["/x/src/ansichten/danke/Danke.svelte"] }),
  ].map((t) => [t.fileName, t]));

  it("hält die Hülle und den Leser mit pdf.js samt Worker vorab, Diagramme und andere Ansichten nicht", () => {
    expect(vorratAus(bau)).toEqual(["/assets/Markdown.js", "/assets/PdfLeser.js", "/assets/barlow.woff2", "/assets/geteilt.js", "/assets/index.css", "/assets/index.js", "/assets/pdf.js", "/assets/pdf.worker.min.mjs"]);
  });

  it("der Dienst nimmt einen fehlenden Vorrat als leer, ein Bau ohne Ersatz bricht nichts", () => {
    const sw = datei("sw.js");
    expect(sw).toContain('const VORRAT = "__VORRAT__";');
    expect(sw).toContain("Array.isArray(VORRAT) ? VORRAT : []");
  });

  it("merkt Bücher nur mit ausdrücklicher Wahl, mit Grenzen, und sagt ohne Netz, warum", () => {
    const sw = datei("sw.js");
    expect(sw).toMatch(/const BUECHER = 5;/);
    expect(sw).toMatch(/const HOECHSTENS_BYTE = 500 \* 1000 \* 1000;/);
    expect(sw).toMatch(/if \(!v\.an\) return;/);
    expect(sw).toMatch(/status: 503/);
  });
});

describe("Kopf der Seite am iPhone", () => {
  const seite = datei("index.html");

  it("Statusleiste über dem Inhalt, nie black-translucent", () => {
    expect(seite).toContain('<meta name="apple-mobile-web-app-status-bar-style" content="default" />');
    expect(seite).not.toMatch(/content="black-translucent"/);
  });

  it("Farbe der Statusleiste je Einstellung des Geräts, wie der Grund der App", () => {
    expect(seite).toMatch(/<meta name="theme-color" content="#[0-9a-f]{6}" media="\(prefers-color-scheme: light\)" \/>/);
    expect(seite).toMatch(/<meta name="theme-color" content="#[0-9a-f]{6}" media="\(prefers-color-scheme: dark\)" \/>/);
  });

  it("jedes Startbild im Kopf liegt vor, hell und dunkel", () => {
    const verweise = [...seite.matchAll(/rel="apple-touch-startup-image"[^>]*href="([^"]+)"/g)].map((m) => m[1]);
    expect(verweise.length).toBeGreaterThanOrEqual(20);
    expect(verweise.filter((v) => v.endsWith("-hell.png")).length).toBe(verweise.length / 2);
    for (const v of verweise) expect(startbilder).toContain(v);
  });
});

describe("Statusleiste folgt der gewählten Darstellung", () => {
  it("aus zwei Angaben für das Gerät wird eine in der Farbe des Grunds", () => {
    document.head.innerHTML = '<meta name="theme-color" content="#d3dedb" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#0b1312" media="(prefers-color-scheme: dark)">';
    document.documentElement.style.setProperty("--grund", "#0b1312");
    darstellung.anwenden();
    const metas = document.querySelectorAll('meta[name="theme-color"]');
    expect(metas.length).toBe(1);
    expect(metas[0].hasAttribute("media")).toBe(false);
    expect((metas[0] as HTMLMetaElement).content).toBe("#0b1312");
  });
});

describe("Gespräch mit dem Dienst im Hintergrund", () => {
  it("ohne Dienst kommt keine Antwort, kein Fehler", async () => {
    expect(await sprich({ art: "lesestoff" })).toBe(null);
  });

  it("fragt über einen eigenen Kanal und nimmt die Antwort", async () => {
    const stand = { an: true, buecher: [{ id: 3, titel: "Probe-PDF", bytes: 29374, zeit: 1 }], bytes: 29374, grenzen: { buecher: 5, bytes: 524288000 } };
    const gesendet: unknown[] = [];
    const active = { postMessage: (n: unknown, [port]: MessagePort[]) => { gesendet.push(n); port.postMessage(stand); } };
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { getRegistration: async () => ({ active }) } });
    expect(await sprich({ art: "lesestoff-an", an: true })).toEqual(stand);
    expect(gesendet).toEqual([{ art: "lesestoff-an", an: true }]);
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: undefined });
  });
});
