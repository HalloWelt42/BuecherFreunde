import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";
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
        if (symbol.purpose !== "maskable") symbol.src = daten(symbol.src.replace(/^\//, ""));
      }
      writeFileSync(ziel, JSON.stringify(manifest));
    },
  };
}

export default defineConfig({
  plugins: [svelte(), tailwindcss(), symbolEinbetten()],
  define: { __FASSUNG__: JSON.stringify(FASSUNG) },
  server: {
    port: 5173,
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
    include: ["tests/**/*.test.js"],
    alias: {
      "$lib": resolve(__dirname, "src/lib"),
    },
  },
});
