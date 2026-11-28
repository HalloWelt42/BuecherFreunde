// Nachbesserung erkannter Seiten aus der Textansicht (BF-118): bitten holt die Seiten neu, ohne Leitstelle sagt eine Meldung warum,
// wählen schaltet die Fassung, und solange Seiten nachgebessert werden, fragt sie im festen Abstand nach
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function aufbau(antwort: unknown) {
  vi.resetModules();
  const gesendet: [string, unknown][] = [];
  vi.stubGlobal("fetch", vi.fn(async (weg: string, o: RequestInit = {}) => {
    gesendet.push([weg, o.body ? JSON.parse(String(o.body)) : null]);
    return weg.endsWith("/fassung") ? new Response(null, { status: 204 }) : new Response(JSON.stringify(antwort));
  }));
  const { Nachbesserung, NACHFRAGE_MS } = await import("../src/lib/leser/pdf/nachbesserung.svelte");
  const { melde } = await import("../src/lib/stand/meldungen.svelte");
  const warn = vi.spyOn(melde, "warn");
  const text = { nachbessernd: [] as number[], erneuert: [] as number[][], async erneuere(nrn: number[]) { this.erneuert.push(nrn); return true; } };
  const n = new Nachbesserung(7, text as never);
  return { n, text, gesendet, warn, NACHFRAGE_MS };
}

describe("Nachbesserung", () => {
  it("bittet für die Seite, holt die genannten Seiten neu und fragt nach, solange sie warten", async () => {
    vi.useFakeTimers();
    const { n, text, gesendet, NACHFRAGE_MS } = await aufbau({ bereit: true, grund: "", seiten: [4, 5, 6] });
    const fertig = n.bitte(4);
    expect(n.arbeit).toBe(4);
    await fertig;
    expect([gesendet[0], text.erneuert, n.arbeit]).toEqual([["/api/books/7/texterkennung/nachbessern", { seite: 4 }], [[4, 5, 6]], null]);
    text.nachbessernd = [5, 6];
    n.pruefe();
    await vi.advanceTimersByTimeAsync(NACHFRAGE_MS);
    expect(text.erneuert.at(-1)).toEqual([5, 6]);
    text.nachbessernd = [];
    await vi.advanceTimersByTimeAsync(NACHFRAGE_MS * 3);
    expect(text.erneuert.length).toBe(2);                                     // nichts wartet mehr: es fragt nicht weiter
    n.halte();
  });

  it("ohne Leitstelle sagt eine Meldung warum, und nichts wird geholt", async () => {
    const { n, text, warn } = await aufbau({ bereit: false, grund: "Keine Leitstelle eingetragen", seiten: [] });
    await n.bitte(2);
    expect([warn.mock.calls, text.erneuert]).toEqual([[["Keine Leitstelle eingetragen"]], []]);
  });

  it("wählt die Fassung einer Seite und holt sie neu", async () => {
    const { n, text, gesendet } = await aufbau({});
    await n.waehle(3, "klassisch");
    expect([gesendet[0], text.erneuert]).toEqual([["/api/books/7/texterkennung/fassung", { seite: 3, gilt: "klassisch" }], [[3]]]);
  });
});
