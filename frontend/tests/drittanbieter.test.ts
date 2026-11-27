// BF-90: Bausteine Dritter aus einer Wahrheit. Die Oberfläche aus der Liste, die der Bau schreibt (build.license, ergänzt in
// vite.config.js), der Server aus seinen installierten Paketen; der Zweck steht je eingetragenem Paket, die Strenge folgt der Lizenz.
import { render, screen } from "@testing-library/svelte";
import { adresseAus, ergaenzt, LIZENZLISTE, ueberAus } from "../vite.config.js";
import { lizenzName, oberflaechenzeilen, pythonName, serverzeilen, strenge, zweckAus, type Baueintrag, type Serverpaket } from "../src/ansichten/einstellungen/drittanbieter";
import zwecke from "../src/ansichten/einstellungen/zwecke.json";
import paket from "../package.json";
import Drittanbieter from "../src/ansichten/einstellungen/Drittanbieter.svelte";

const anforderungen = Object.values(import.meta.glob<string>("../../backend/requirements.txt", { query: "?raw", import: "default", eager: true }))[0];

describe("Zweck je eingetragenem Paket", () => {
  it("nennt jedes Paket aus package.json und nur eingetragene", () => {
    const eingetragen = new Set(Object.keys({ ...paket.dependencies, ...paket.devDependencies }));
    expect(Object.keys(zwecke.oberflaeche).filter((n) => !eingetragen.has(n))).toEqual([]);
    expect(Object.keys(paket.dependencies).filter((n) => !(n in zwecke.oberflaeche))).toEqual([]);
  });

  it("nennt genau die Pakete aus requirements.txt", () => {
    const namen = anforderungen.split("\n").map((z) => z.replace(/(?:^|\s)#.*$/, "").trim()).filter((z) => z && !z.startsWith("-"))
      .map((z) => pythonName(/^[A-Za-z0-9][A-Za-z0-9._-]*/.exec(z)?.[0] ?? ""));
    expect(Object.keys(zwecke.server).sort()).toEqual([...new Set(namen)].sort());
  });

  it("ein eingetragenes Paket mit seinem Zweck, jedes andere für die, über die es kommt", () => {
    const eigene = { mermaid: "Diagramme", pymupdf: "PDF" };
    expect(zweckAus("mermaid", ["mermaid"], eigene)).toBe("Diagramme");
    expect(zweckAus("d3-shape", ["mermaid", "appkern-oberflaeche"], eigene)).toBe("für mermaid, appkern-oberflaeche");
    expect(zweckAus("PyMuPDF", ["PyMuPDF"], eigene, pythonName)).toBe("PDF");
    expect(zweckAus("pytest", [], eigene)).toBe("");
    expect(pythonName("Typing_Extensions")).toBe("typing-extensions");
  });

  it("macht aus beiden Listen Zeilen derselben Form", () => {
    const bau: Baueintrag[] = [{ name: "samtpfote", version: "0.2.0", identifier: "SEE LICENSE IN LIZENZ.txt", text: "Nutzungsbedingungen", adresse: "", ueber: ["samtpfote"] }];
    expect(oberflaechenzeilen(bau)).toEqual([{ schluessel: "samtpfote@0.2.0", name: "samtpfote", fassung: "0.2.0", lizenz: "siehe LIZENZ.txt", adresse: "", zweck: zwecke.oberflaeche.samtpfote }]);
    const server: Serverpaket[] = [{ name: "starlette", fassung: "0.41.3", lizenz: "", adresse: "https://example.org", ueber: ["appkern", "fastapi"] }];
    expect(serverzeilen(server)[0]).toMatchObject({ schluessel: "starlette@0.41.3", lizenz: "ohne Kennung", zweck: "für appkern, fastapi" });
  });
});

describe("Lizenzen", () => {
  it("ordnet nach Strenge", () => {
    expect(strenge("MIT")).toBe("gut");
    expect(strenge("LGPL-3.0")).toBe("warn");
    expect(strenge("AGPL-3.0")).toBe("schlecht");
    expect(strenge("GPL-3.0")).toBe("schlecht");
  });

  it("liest SPDX-Ausdrücke: OR die freieste Wahl, AND die strengste", () => {
    expect(strenge("(MPL-2.0 OR Apache-2.0)")).toBe("gut");
    expect(strenge("MPL-2.0 AND MIT")).toBe("warn");
    expect(strenge("(CC-BY-4.0 AND OFL-1.1 AND MIT)")).toBe("gut");
    expect(strenge("LicenseRef-Appkern-NC-1.0 OR AGPL-3.0-only")).toBe("schlecht");
    expect(strenge("MIT OR (GPL-3.0-only AND LGPL-3.0)")).toBe("gut");
  });

  it("liest auch Angaben in Worten, wie Pakete sie machen", () => {
    expect(strenge("GNU Affero General Public License")).toBe("schlecht");
    expect(strenge("Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License")).toBe("schlecht");
    expect(strenge("GNU General Public License v3 (GPLv3)")).toBe("schlecht");
    expect(strenge("GNU Lesser General Public License v3 (LGPLv3)")).toBe("warn");
    expect(strenge("LGPL v3")).toBe("warn");
    expect(strenge("Mozilla Public License 2.0 (MPL 2.0)")).toBe("warn");
    for (const frei of ["MIT-CMU", "PSF-2.0", "Apache License, Version 2.0", "ISC", "BSD-2-Clause", "MIT License", "OFL-1.1"]) expect(strenge(frei)).toBe("gut");
  });

  it("sagt zu eigenen und unbekannten Lizenzen nichts", () => {
    for (const offen of ["LicenseRef-Appkern-NC-1.0", "LicenseRef-Beispiel AND MIT", "siehe LIZENZ.txt", "ohne Kennung", "Artifex Commercial License"]) expect(strenge(offen)).toBe("");
  });

  it("nennt eine eigene Datei und fehlende Kennungen", () => {
    expect(lizenzName("SEE LICENSE IN LIZENZ.txt")).toBe("siehe LIZENZ.txt");
    expect(lizenzName("MIT")).toBe("MIT");
    expect(lizenzName(undefined)).toBe("ohne Kennung");
    expect(lizenzName(" ")).toBe("ohne Kennung");
  });
});

describe("Liste des Baus", () => {
  it("findet die Adresse in package.json", () => {
    expect(adresseAus({ homepage: "https://example.org/paket#readme", repository: "github:a/b" })).toBe("https://example.org/paket");
    expect(adresseAus({ repository: "github:a/b" })).toBe("https://github.com/a/b");
    expect(adresseAus({ repository: { url: "git+https://github.com/a/b.git" } })).toBe("https://github.com/a/b");
    expect(adresseAus({ repository: { url: "git+ssh://git@github.com/a/b.git" } })).toBe("https://github.com/a/b");
    expect(adresseAus({ repository: "git://github.com/a/b.git" })).toBe("https://github.com/a/b");
    expect(adresseAus({ repository: "a/b" })).toBe("https://github.com/a/b");
    expect(adresseAus({ repository: "gitlab:a/b" })).toBe("");
    expect(adresseAus({})).toBe("");
  });

  it("führt jedes Paket auf die eingetragenen zurück, über die es kommt, auch über weitere und im Kreis", () => {
    const einbinder = new Map([
      ["d3-shape@3.2.0", new Set(["d3@7.9.0"])],
      ["d3@7.9.0", new Set(["mermaid@11.13.0"])],
      ["marked@16.4.2", new Set(["mermaid@11.13.0"])],
      ["marked@17.0.6", new Set(["@humanspeak/svelte-markdown@1.0.5"])],
      ["a@1.0.0", new Set(["b@1.0.0"])],
      ["b@1.0.0", new Set(["a@1.0.0"])],
    ]);
    const pakete = ["mermaid@11.13.0", "d3-shape@3.2.0", "marked@16.4.2", "marked@17.0.6", "a@1.0.0"];
    const ueber = ueberAus(pakete, einbinder, new Set(["mermaid", "@humanspeak/svelte-markdown"]));
    expect(Object.fromEntries(ueber)).toEqual({
      "mermaid@11.13.0": ["mermaid"], "d3-shape@3.2.0": ["mermaid"], "marked@16.4.2": ["mermaid"], "marked@17.0.6": ["@humanspeak/svelte-markdown"], "a@1.0.0": [],
    });
  });

  it("holt den Text aus der eigenen Datei des Pakets und die Kennung aus seinem Text", () => {
    const gelesen: string[] = [];
    const lesen = (pfad: string) => (gelesen.push(pfad), "Nutzungsbedingungen der Katze");
    const katze = ergaenzt({ name: "katze", version: "1.0.0", identifier: "SEE LICENSE IN LIZENZ.txt" }, { ordner: "/x/katze", daten: {} }, ["katze"], lesen);
    expect(katze).toEqual({ name: "katze", version: "1.0.0", identifier: "SEE LICENSE IN LIZENZ.txt", text: "Nutzungsbedingungen der Katze", adresse: "", ueber: ["katze"] });
    expect(gelesen).toEqual(["/x/katze/LIZENZ.txt"]);
    const eigen = ergaenzt({ name: "kern", version: "0.0.0", text: "Eigene Lizenz\nSPDX-License-Identifier: LicenseRef-Kern-1.0\n" }, undefined, ["kern"], lesen);
    expect(eigen.identifier).toBe("LicenseRef-Kern-1.0");
    const mit = ergaenzt({ name: "x", version: "1", identifier: "MIT", text: "MIT License" }, { ordner: "/x", daten: { repository: "a/b" } }, [], lesen);
    expect(mit).toMatchObject({ identifier: "MIT", text: "MIT License", adresse: "https://github.com/a/b" });
    expect(gelesen).toHaveLength(1);
  });
});

describe("Seite Drittanbieter", () => {
  const bau: Baueintrag[] = [
    { name: "mermaid", version: "11.13.0", identifier: "MIT", text: "MIT License", adresse: "https://example.org/mermaid", ueber: ["mermaid"] },
    { name: "d3-shape", version: "3.2.0", identifier: "ISC", text: "ISC License", adresse: "", ueber: ["mermaid"] },
  ];
  const server: Serverpaket[] = [{ name: "EbookLib", fassung: "0.18", lizenz: "GNU Affero General Public License", adresse: "https://example.org/ebooklib", ueber: ["EbookLib"] }];

  function netz(liste: Response) {
    globalThis.fetch = vi.fn((weg: string) =>
      Promise.resolve(weg === `/${LIZENZLISTE}` ? liste : new Response(JSON.stringify(server), { status: 200, headers: { "content-type": "application/json" } }))) as unknown as typeof fetch;
  }

  it("zeigt beide Listen mit Fassung, Lizenz und Zweck", async () => {
    netz(new Response(JSON.stringify(bau), { status: 200, headers: { "content-type": "application/json" } }));
    render(Drittanbieter);
    expect(await screen.findByText("EbookLib")).toBeTruthy();
    expect(screen.getByText(zwecke.server.ebooklib)).toBeTruthy();
    expect(screen.getByText("GNU Affero General Public License").className).toContain("schlecht");
    expect(await screen.findByText("d3-shape")).toBeTruthy();
    expect(screen.getByText("für mermaid")).toBeTruthy();
    expect(screen.getByText("3.2.0")).toBeTruthy();
    expect(screen.getByText("mermaid").closest("a")?.getAttribute("href")).toBe("https://example.org/mermaid");
    expect(screen.getByText("d3-shape").closest("a")).toBeNull();
  });

  it("sagt ohne Bau, dass die Liste der Oberfläche erst beim Bau entsteht", async () => {
    netz(new Response("<!doctype html>", { status: 200, headers: { "content-type": "text/html" } }));
    render(Drittanbieter);
    expect(await screen.findByText(/Oberfläche: Die Liste der Oberfläche entsteht erst beim Bau/)).toBeTruthy();
    expect(await screen.findByText("EbookLib")).toBeTruthy();
  });
});
