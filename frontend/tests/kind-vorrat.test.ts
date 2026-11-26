// Ohne Netz (BF-78): der Kinderbereich und die Trennmuster seiner Silben liegen im Vorrat des Dienstes im Hintergrund
import { vorratAus } from "../vite.config.js";

function teil(fileName: string, ueber: Record<string, unknown> = {}) {
  return { type: "chunk", fileName, isEntry: false, imports: [], dynamicImports: [], moduleIds: [], viteMetadata: { importedCss: new Set(), importedAssets: new Set() }, ...ueber };
}

describe("Vorrat ohne Netz", () => {
  it("nimmt die Silben, die der Kinderbereich erst bei Bedarf lädt, mit in den Vorrat", () => {
    const bau = Object.fromEntries([
      teil("assets/index.js", { isEntry: true, dynamicImports: ["assets/Kinderleser.js", "assets/Einstellungen.js"], moduleIds: ["/x/src/main.ts"] }),
      teil("assets/Kinderleser.js", { dynamicImports: ["assets/de-1996.js"], moduleIds: ["/x/src/ansichten/kind/Kinderleser.svelte", "/x/src/lib/kind/silben.ts"] }),
      teil("assets/de-1996.js", { moduleIds: ["/x/node_modules/hyphen/de-1996/index.js", "/x/node_modules/hyphen/patterns/de-1996.js"] }),
      teil("assets/Einstellungen.js", { moduleIds: ["/x/src/ansichten/einstellungen/Einstellungen.svelte"] }),
    ].map((t) => [t.fileName, t]));
    expect(vorratAus(bau)).toEqual(["/assets/Kinderleser.js", "/assets/de-1996.js", "/assets/index.js"]);
  });

  it("nimmt die Trennmuster auch, wenn der Kinderbereich fest im Einstieg steckt", () => {
    const bau = Object.fromEntries([
      teil("assets/index.js", { isEntry: true, dynamicImports: ["assets/de-1996.js"], moduleIds: ["/x/src/main.ts", "/x/src/lib/kind/silben.ts"] }),
      teil("assets/de-1996.js", { moduleIds: ["/x/node_modules/hyphen/patterns/de-1996.js"] }),
    ].map((t) => [t.fileName, t]));
    expect(vorratAus(bau)).toEqual(["/assets/de-1996.js", "/assets/index.js"]);
  });
});
