import { afterEach, describe, expect, it, vi } from "vitest";
import { ladefehler } from "../src/lib/leser/ladefehler";

const antworte = (status: number, inhalt: unknown) => vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(inhalt), { status })));

afterEach(() => vi.unstubAllGlobals());

describe("ladefehler", () => {
  it("nennt den Grund des Servers und bietet die Datei dann nicht an", async () => {
    antworte(404, { detail: "Dieses Buch liegt noch nicht in der Kellerwolke" });
    expect(await ladefehler(2334)).toEqual({ text: "Dieses Buch liegt noch nicht in der Kellerwolke", dateiDa: false });
  });
  it("gibt der Server die Datei her, liegt es an ihr", async () => {
    antworte(206, {});
    expect(await ladefehler(1)).toEqual({ text: "Die Datei ließ sich nicht lesen", dateiDa: true });
  });
  it("nennt nie eine Adresse", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch https://x/api?token=geheim"); }));
    const f = await ladefehler(1);
    expect(f.text).toBe("Keine Verbindung zur Bibliothek");
  });
});
