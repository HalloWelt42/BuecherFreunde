import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve, dirname, join } from "path";
import { fileURLToPath } from "url";
import { readFileSync, writeFileSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Fassung der gebauten Oberfläche; weicht die des Servers ab, lädt die Seite neu (lib/fassung.svelte.js)
const FASSUNG = readFileSync(resolve(__dirname, "../VERSION"), "utf-8").trim();

// Bausteine Dritter im Bündel (BF-90): build.license schreibt die Liste beim Bau, je Paket mit Fassung, Lizenz und Lizenztext;
// die Seite Drittanbieter liest sie von dort. Pakete aus package.json stehen für sich, alle anderen kommen über sie hinein.
export const LIZENZLISTE = "drittanbieter.json";
const PAKET = JSON.parse(readFileSync(resolve(__dirname, "package.json"), "utf-8"));
const EINGETRAGEN = new Set(Object.keys({ ...PAKET.dependencies, ...PAKET.devDependencies }));
const EIGENE_DATEI = /^SEE LICENSE IN ([\w.-]+)$/i;
const SPDX_ZEILE = /SPDX-License-Identifier:\s*(\S.*?)\s*$/m;

const paketname = (schluessel) => schluessel.slice(0, schluessel.lastIndexOf("@"));

/** Wo ein Paket im Netz steht, nach seiner package.json (homepage, sonst repository); leer ohne Angabe */
export function adresseAus(daten) {
  const roh = daten.homepage || (typeof daten.repository === "string" ? daten.repository : daten.repository?.url) || "";
  const adresse = roh.trim().replace(/^git\+/, "").replace(/^github:/, "https://github.com/").replace(/^(?:git|ssh):\/\/(?:git@)?/, "https://")
    .replace(/^git@([^:]+):/, "https://$1/").replace(/#.*$/, "").replace(/\.git$/, "");
  if (/^[\w.-]+\/[\w.-]+$/.test(adresse)) return `https://github.com/${adresse}`;
  return /^https?:\/\//.test(adresse) ? adresse : "";
}

/** Je Paket (name@fassung) die Pakete aus package.json, über die es ins Bündel kommt, auch über weitere; ein eingetragenes
 *  nur sich selbst. `einbinder`: je Paket die Pakete, die eines seiner Module einbinden (eigener Code zählt nicht). */
export function ueberAus(pakete, einbinder, eingetragen) {
  return new Map(pakete.map((paket) => {
    if (eingetragen.has(paketname(paket))) return [paket, [paketname(paket)]];
    const gefunden = new Set();
    const gesehen = new Set([paket]);
    const offen = [paket];
    while (offen.length) {
      for (const von of einbinder.get(offen.pop()) ?? []) {
        if (gesehen.has(von)) continue;
        gesehen.add(von);
        if (eingetragen.has(paketname(von))) gefunden.add(paketname(von));
        else offen.push(von);
      }
    }
    return [paket, [...gefunden].sort()];
  }));
}

/** Ein Eintrag von build.license mit dem, was die Seite braucht: der Lizenztext aus der eigenen Datei des Pakets ("SEE LICENSE
 *  IN"), die Kennung aus der Zeile SPDX-License-Identifier, wo package.json keine nennt, Adresse und `ueber` */
export function ergaenzt(eintrag, paket, ueber, lesen) {
  const datei = EIGENE_DATEI.exec(eintrag.identifier ?? "")?.[1];
  const text = eintrag.text ?? (datei && paket ? lesen(join(paket.ordner, datei)) : undefined);
  const identifier = eintrag.identifier ?? SPDX_ZEILE.exec(text ?? "")?.[1];
  return { ...eintrag, identifier, text, adresse: adresseAus(paket?.daten ?? {}), ueber };
}

/** Das Paket eines Moduls, wie build.license es findet: die nächste package.json mit Namen über dem Modul */
function paketsucher() {
  const jeOrdner = new Map();
  const suche = (ordner) => {
    if (!jeOrdner.has(ordner)) {
      let fund = null;
      try {
        const daten = JSON.parse(readFileSync(join(ordner, "package.json"), "utf-8"));
        if (daten.name) fund = { schluessel: `${daten.name}@${daten.version ?? "0.0.0"}`, ordner, daten };
      } catch {
        // hier liegt keine package.json
      }
      jeOrdner.set(ordner, fund ?? (dirname(ordner) === ordner ? null : suche(dirname(ordner))));
    }
    return jeOrdner.get(ordner);
  };
  return (id) => (id.startsWith("\0") || !id.includes("node_modules") ? null : suche(dirname(id)));
}

function lesen(pfad) {
  try {
    return readFileSync(pfad, "utf-8").trim();
  } catch {
    return undefined;
  }
}

// Ergänzt die Liste, nachdem build.license sie geschrieben hat (order "post"). Wer wen einbindet, sagt der Modulgraph; durch
// Module desselben Pakets und erzeugte Module geht es weiter, denn ein Paket wird oft über seinen Einstieg eingebunden, der
// nur weiterreicht und darum selbst nicht im Bündel steht.
function drittanbieterListe() {
  return {
    name: "drittanbieter-liste",
    apply: "build",
    generateBundle: {
      order: "post",
      handler(_optionen, bundle) {
        const liste = bundle[LIZENZLISTE];
        if (liste?.type !== "asset") return;
        const paketVon = paketsucher();
        const pakete = new Map();
        const einbinder = new Map();
        const gesehen = new Set();
        const folge = (id, ziel) => {
          if (gesehen.has(`${ziel}|${id}`)) return;
          gesehen.add(`${ziel}|${id}`);
          const info = this.getModuleInfo(id);
          for (const von of [...(info?.importers ?? []), ...(info?.dynamicImporters ?? [])]) {
            const quelle = von.startsWith("\0") ? ziel : paketVon(von)?.schluessel;
            if (quelle === ziel) folge(von, ziel);
            else if (quelle) einbinder.set(ziel, (einbinder.get(ziel) ?? new Set()).add(quelle));
          }
        };
        for (const teil of Object.values(bundle)) {
          if (teil.type !== "chunk") continue;
          for (const id of teil.moduleIds) {
            const ziel = paketVon(id);
            if (!ziel) continue;
            pakete.set(ziel.schluessel, ziel);
            folge(id, ziel.schluessel);
          }
        }
        const eintraege = JSON.parse(String(liste.source));
        const schluessel = eintraege.map((e) => `${e.name}@${e.version}`);
        const ueber = ueberAus(schluessel, einbinder, EINGETRAGEN);
        liste.source = JSON.stringify(eintraege.map((e, i) => ergaenzt(e, pakete.get(schluessel[i]), ueber.get(schluessel[i]) ?? [], lesen)), null, 2);
      },
    },
  };
}

// Das iPhone holt Symbole für den Home-Bildschirm nicht zuverlässig über eine Adresse; eingebettet als data:-Adresse
// zeigt es sie. Quelle bleiben die PNG in public/ (tools/symbole.py).
function symbolEinbetten() {
  const daten = (datei) => `data:image/png;base64,${readFileSync(resolve(__dirname, "public", datei)).toString("base64")}`;
  return {
    name: "symbol-einbetten",
    apply: "build",
    transformIndexHtml: (html) => html.replace('href="/apple-touch-icon.png"', `href="${daten("apple-touch-icon.png")}"`),
    writeBundle(optionen) {
      const ziel = `${optionen.dir}/site.webmanifest`;
      const manifest = JSON.parse(readFileSync(ziel, "utf-8"));
      for (const symbol of manifest.icons ?? []) {
        if (symbol.purpose === "any") symbol.src = daten(symbol.src.replace(/^\//, ""));
      }
      writeFileSync(ziel, JSON.stringify(manifest));
    },
  };
}

// Module, die der Leser ohne Netz nie braucht oder die zu groß sind: Diagramme in Markdown laden erst bei Bedarf
const OHNE_VORRAT = /node_modules\/(?:mermaid|@mermaid-js|cytoscape|katex|elkjs)\//;
// Der Leser, der Kinderbereich und die Trennmuster seiner Silben (lib/kind/silben.ts lädt sie erst bei Bedarf)
const LESER = /\/src\/(?:ansichten|lib)\/(?:leser|kind)\/|\/node_modules\/hyphen\//;

/** Was der Dienst im Hintergrund vorab speichert: die Hülle der App (alles, was der Einstieg fest lädt) und der Leser mit
 *  allen Formaten (pdf.js samt Worker, foliate-js, Textleser), dazu ihr Stil, ihre Schriften und Bilder */
export function vorratAus(bundle) {
  const teile = new Map(Object.values(bundle).filter((t) => t.type === "chunk").map((t) => [t.fileName, t]));
  const aus = new Set();
  const nimm = (name, mitNachgeladenem) => {
    const t = teile.get(name);
    if (!t || aus.has(name) || t.moduleIds.some((m) => OHNE_VORRAT.test(m))) return;
    aus.add(name);
    for (const datei of [...(t.viteMetadata?.importedCss ?? []), ...(t.viteMetadata?.importedAssets ?? [])]) aus.add(datei);
    for (const i of t.imports) nimm(i, mitNachgeladenem);
    for (const d of t.dynamicImports) if (mitNachgeladenem || teile.get(d)?.moduleIds.some((m) => LESER.test(m))) nimm(d, true);
  };
  for (const t of teile.values()) if (t.isEntry) nimm(t.fileName, false);
  return [...aus].sort().map((datei) => `/${datei}`);
}

// Der Dienst im Hintergrund (public/sw.js) trägt die Fassung, so räumt eine neue die alte Hülle weg, und seinen Vorrat
function dienstFassung() {
  let vorrat = [];
  return {
    name: "dienst-fassung",
    apply: "build",
    generateBundle(_optionen, bundle) {
      vorrat = vorratAus(bundle);
    },
    writeBundle(optionen) {
      const ziel = `${optionen.dir}/sw.js`;
      writeFileSync(ziel, readFileSync(ziel, "utf-8").replace("__FASSUNG__", FASSUNG).replace('"__VORRAT__"', JSON.stringify(vorrat)));
    },
  };
}

// Sicherheitsköpfe samt Content-Security-Policy wie im Betrieb, aus derselben Datei wie nginx (BF-5): ein Verstoß zeigt sich
// schon beim Entwickeln
const SICHERHEIT = Object.fromEntries(
  [...readFileSync(resolve(__dirname, "../docker/sicherheit.conf"), "utf-8").matchAll(/^add_header\s+(\S+)\s+"([^"]*)"\s+always;/gm)].map((m) => [m[1], m[2]]),
);

export default defineConfig({
  plugins: [svelte(), symbolEinbetten(), dienstFassung(), drittanbieterListe()],
  define: { __FASSUNG__: JSON.stringify(FASSUNG), __LIZENZLISTE__: JSON.stringify(`/${LIZENZLISTE}`) },
  preview: { headers: SICHERHEIT },
  server: {
    port: 5173,
    headers: SICHERHEIT,
    fs: {
      allow: [resolve(__dirname, "..")],
    },
    proxy: {
      "/api": {
        // API_ZIEL: anderes Backend für die Entwicklung, etwa der Pi (http://<pi>:8160)
        target: process.env.API_ZIEL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    license: { fileName: LIZENZLISTE },
  },
  resolve: {
    conditions: ["browser"],
  },
  // Der Editor des Appkerns (appkern-oberflaeche/code, BF-29) kommt als Svelte-Quelltext und wird wie eigener Code
  // übersetzt; CodeMirror nur einmal vorgebündelt, sonst greifen Erweiterungen und Farben nicht (zwei Fassungen von state)
  optimizeDeps: {
    exclude: ["appkern-oberflaeche"],
    include: [
      "@codemirror/autocomplete", "@codemirror/commands", "@codemirror/lang-css", "@codemirror/lang-html",
      "@codemirror/lang-javascript", "@codemirror/lang-markdown", "@codemirror/lang-php", "@codemirror/lang-python",
      "@codemirror/lang-sql", "@codemirror/language", "@codemirror/lint", "@codemirror/search", "@codemirror/state",
      "@codemirror/view", "@lezer/common", "@lezer/highlight",
    ],
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.js"],
    include: ["tests/**/*.test.{js,ts}"],
    alias: {
      "$lib": resolve(__dirname, "src/lib"),
    },
  },
});
