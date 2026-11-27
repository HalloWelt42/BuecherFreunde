// BF-102: Lädt ein Bild aus den Inhalten nicht (Cookie für Inhalte fehlt), erneuert die App einmal den Zugang und lädt neu;
// erst wenn es dann nicht kommt, gibt sie auf.
import { inhaltsbild, NEU_GELADEN } from "../src/lib/inhaltsbild";

describe("Inhaltsbild", () => {
  it("erneuert bei einem Fehler einmal den Zugang und lädt das Bild neu", async () => {
    const aufrufe: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (weg: string, o: RequestInit = {}) => {
      aufrufe.push(`${o.method ?? "GET"} ${weg}`);
      return new Response(null, { status: 204 });
    }));
    const bild = document.createElement("img");
    bild.src = "/api/books/7/textseiten/41/bild/0";
    let aufgegeben = 0;
    const a = inhaltsbild(bild, () => aufgegeben++);
    bild.dispatchEvent(new Event("error"));
    await vi.waitFor(() => expect(new URL(bild.src).searchParams.has(NEU_GELADEN)).toBe(true));
    expect(aufrufe).toEqual(["POST /api/anmeldung/zugang"]);
    expect(new URL(bild.src).pathname).toBe("/api/books/7/textseiten/41/bild/0");
    bild.dispatchEvent(new Event("error"));                      // auch neu geladen kam es nicht: aufgeben
    expect(aufgegeben).toBe(1);
    expect(aufrufe).toHaveLength(1);
    a.destroy();
    vi.unstubAllGlobals();
  });

  it("eingebettete Bilder geben gleich auf, ohne den Zugang zu fragen", () => {
    const abruf = vi.fn();
    vi.stubGlobal("fetch", abruf);
    const bild = document.createElement("img");
    bild.src = "data:image/png;base64,AAAA";
    let aufgegeben = 0;
    inhaltsbild(bild, () => aufgegeben++);
    bild.dispatchEvent(new Event("error"));
    expect([aufgegeben, abruf.mock.calls.length]).toEqual([1, 0]);
    vi.unstubAllGlobals();
  });
});
