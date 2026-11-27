// BF-108: Bleibt der Server bei sichtbarer Seite weg, lädt sie sich einmal selbst neu (neue Verbindungen), aber nie in einer
// Schleife; kommt er zurück, beginnt das Zählen von vorn.
import { NEU_LADEN_NACH, Netz } from "../src/lib/stand/netz.svelte";

describe("Netz", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it("lädt nach mehreren vergeblichen Nachfragen einmal neu, danach nicht gleich wieder", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Load failed"))));
    const neu = vi.fn();
    const n = new Netz(neu);
    for (let i = 0; i < NEU_LADEN_NACH - 1; i++) await n.pruefe();
    expect(neu).not.toHaveBeenCalled();
    await n.pruefe();
    expect(neu).toHaveBeenCalledOnce();
    const zweite = new Netz(neu);
    for (let i = 0; i < NEU_LADEN_NACH * 2; i++) await zweite.pruefe();
    expect(neu).toHaveBeenCalledOnce();                            // höchstens einmal in einer Weile
  });

  it("eine Antwort setzt das Zählen zurück", async () => {
    let gut = false;
    vi.stubGlobal("fetch", vi.fn(async () => (gut ? new Response("{}") : Promise.reject(new TypeError("Load failed")))));
    const neu = vi.fn();
    const n = new Netz(neu);
    for (let i = 0; i < NEU_LADEN_NACH - 1; i++) await n.pruefe();
    gut = true;
    await n.pruefe();
    gut = false;
    for (let i = 0; i < NEU_LADEN_NACH - 1; i++) await n.pruefe();
    expect(neu).not.toHaveBeenCalled();
  });
});
