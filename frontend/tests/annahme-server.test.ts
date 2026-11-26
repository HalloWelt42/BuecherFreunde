// BF-50: Folgen in der Oberfläche: Herunterladen als Anhang, Aufräumen am Server in einem Schritt
import { alsAnhang, dateiUrl, ladeUrl } from "../src/lib/api/books";
import { raeumeAnnahmeAuf } from "../src/lib/api/annahme";

const sw = Object.values(import.meta.glob<string>("../public/sw.js", { query: "?raw", import: "default", eager: true }))[0];

describe("Herunterladen und Ansehen", () => {
  it("Ansehen bleibt bei der einfachen Adresse, Herunterladen bittet um einen Anhang", () => {
    expect(dateiUrl(7)).toBe("/api/books/7/file");
    expect(ladeUrl(7)).toBe("/api/books/7/file?herunterladen=true");
    expect(alsAnhang("/api/books/7/file?x=1")).toBe("/api/books/7/file?x=1&herunterladen=true");
  });

  it("der Dienst im Hintergrund merkt Herunterladen nie als Lesestoff", () => {
    expect(sw).toContain('ziel.searchParams.has("herunterladen") ? null : ZUM_BUCH.exec(ziel.pathname)');
  });
});

describe("Aufräumen der Annahme", () => {
  it("in einem Schritt nach Quelle und Ständen", async () => {
    const wege: [string, string][] = [];
    globalThis.fetch = vi.fn((weg: string, optionen: RequestInit = {}) => {
      wege.push([optionen.method ?? "GET", String(weg)]);
      return Promise.resolve(new Response(JSON.stringify({ entfernt: 3, eintraege: [], zaehler: { alle: 0, laeuft: 0, klaeren: 0, da: 0, fertig: 0 }, quellen: {} })));
    }) as unknown as typeof fetch;
    const antwort = await raeumeAnnahmeAuf("ordner", ["fertig", "da"]);
    expect(antwort.entfernt).toBe(3);
    expect(wege).toEqual([["DELETE", "/api/annahme?quelle=ordner&stand=fertig&stand=da"]]);
  });
});
