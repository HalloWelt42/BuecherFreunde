import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { readFileSync, writeFileSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Fassung der gebauten Oberfläche; weicht die des Servers ab, lädt die Seite neu (lib/fassung.svelte.js)
const FASSUNG = readFileSync(resolve(__dirname, "../VERSION"), "utf-8").trim();

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

// Der Dienst im Hintergrund (public/sw.js) trägt die Fassung, so räumt eine neue die alte Hülle weg
function dienstFassung() {
  return {
    name: "dienst-fassung",
    apply: "build",
    writeBundle(optionen) {
      const ziel = `${optionen.dir}/sw.js`;
      writeFileSync(ziel, readFileSync(ziel, "utf-8").replace("__FASSUNG__", FASSUNG));
    },
  };
}

// Sicherheitsköpfe samt Content-Security-Policy wie im Betrieb, aus derselben Datei wie nginx (BF-5): ein Verstoß zeigt sich
// schon beim Entwickeln
const SICHERHEIT = Object.fromEntries(
  [...readFileSync(resolve(__dirname, "../docker/sicherheit.conf"), "utf-8").matchAll(/^add_header\s+(\S+)\s+"([^"]*)"\s+always;/gm)].map((m) => [m[1], m[2]]),
);

export default defineConfig({
  plugins: [svelte(), symbolEinbetten(), dienstFassung()],
  define: { __FASSUNG__: JSON.stringify(FASSUNG) },
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
  },
  resolve: {
    conditions: ["browser"],
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
