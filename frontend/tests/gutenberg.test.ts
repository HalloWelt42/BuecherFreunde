import { beforeEach, describe, expect, it, vi } from "vitest";
import { gutenberg } from "../src/lib/stand/gutenberg.svelte";

const buch = (n: number) => ({ gutenberg_id: n, titel: `Buch ${n}`, autor: "", sprachen: ["de"], download_url: "x", download_format: "epub", cover_url: "", download_count: 0 });

function antworte(seiten: Record<number, number[]>) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(async (adresse: string) => {
    const seite = Number(new URL(adresse, "http://x").searchParams.get("seite"));
    const buecher = (seiten[seite] ?? []).map(buch);
    return { ok: true, status: 200, json: async () => ({ gesamt: 4, seite, naechste: seiten[seite + 1] ? "x" : null, vorherige: null, buecher }) };
  });
}

describe("Gemeinfreie Bücher: Auswahl", () => {
  beforeEach(() => antworte({ 1: [1, 2], 2: [3, 4] }));

  // Seit BF-98 bleibt die Auswahl auch über eine neue Suche: aus den Vorschlägen Gewähltes gilt weiter, während Gutendex gefragt wird
  it("behält die Auswahl beim Blättern und bei neuer Suche, bis sie aufgehoben wird", async () => {
    await gutenberg.suche();
    gutenberg.schalte(gutenberg.treffer[0]);
    await gutenberg.blaettere(1);
    expect(gutenberg.weitere).toBe(false);
    expect(gutenberg.seite).toBe(2);
    gutenberg.schalteSeite();
    expect(gutenberg.zahl).toBe(3);
    expect(gutenberg.hat(1)).toBe(true);
    gutenberg.schalteSeite();
    expect(gutenberg.zahl).toBe(1);
    await gutenberg.suche();
    expect(gutenberg.zahl).toBe(1);
    gutenberg.leere();
    expect(gutenberg.zahl).toBe(0);
  });
});
