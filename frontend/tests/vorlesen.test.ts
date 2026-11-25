import { beforeEach, describe, expect, it, vi } from "vitest";
import { saetze } from "../src/lib/vorlesen/saetze";
import { zeilenAus } from "../src/lib/vorlesen/zeilen";
import { Vorlauf } from "../src/lib/vorlesen/vorlauf";

const antwort = { da: true, hinweis: "", stimmen: [{ id: "anna", name: "Anna", gruppe: "eigene" }, { id: "katalog:b", name: "Bert", gruppe: "eingebaut" }] };

async function frisch(dienst: unknown) {
  vi.resetModules();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(dienst))));
  const { vorlesen } = await import("../src/lib/stand/vorlesen.svelte");
  vorlesen.pruefe();
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
  await new Promise((r) => setTimeout(r, 5));
  return vorlesen;
}

beforeEach(() => localStorage.clear());

describe("Stimmenauswahl", () => {
  it("bietet die Stimmen des Sprechdienstes in Gruppen, zuerst die Vorgabe", async () => {
    const v = await frisch(antwort);
    expect(v.stimme).toBe("dienst:");
    expect(v.gruppen.map(([g]) => g)).toEqual(["Sprechdienst", "Eigene Stimmen", "Eingebaute Stimmen", "Dieses Gerät"]);
  });
  it("merkt sich die Wahl auf dem Gerät", async () => {
    (await frisch(antwort)).waehle("dienst:anna");
    expect((await frisch(antwort)).stimme).toBe("dienst:anna");
  });
  it("ohne Sprechdienst gelten die übrigen Stimmen, eine verschwundene Wahl fällt weg", async () => {
    localStorage.setItem("vorlesen.stimme", "dienst:anna");
    const v = await frisch({ da: false, stimmen: [], hinweis: "" });
    expect(v.stimmen.every((s) => !s.id.startsWith("dienst:"))).toBe(true);
    expect(v.stimme).toBe("pappagei:");
  });
});

describe("Text teilen", () => {
  it("an Satzenden, überlange an Wortgrenzen", () => {
    expect(saetze("Erster Satz. Zweiter!\nDritter?")).toEqual(["Erster Satz.", "Zweiter!", "Dritter?"]);
    const lang = saetze("wort ".repeat(120));
    expect(lang.every((s) => s.length <= 220)).toBe(true);
    expect(lang.join(" ").split(" ").length).toBe(120);
  });
});

describe("Strom", () => {
  it("liest Zeilen auch über Stückgrenzen hinweg", async () => {
    const stuecke = ['{"art":"sa', 'tz"}\n{"art":', '"ende"}'].map((s) => new TextEncoder().encode(s));
    const strom = new ReadableStream<Uint8Array>({ start: (c) => (stuecke.forEach((s) => c.enqueue(s)), c.close()) });
    const aus: unknown[] = [];
    for await (const z of zeilenAus(strom)) aus.push(z);
    expect(aus).toEqual([{ art: "satz" }, { art: "ende" }]);
  });
  it("nach einem Abriss wartet er länger, nach ruhigem Lauf wieder kürzer", () => {
    const v = new Vorlauf();
    expect(v.genug(1, false)).toBe(false);
    expect(v.genug(1, true)).toBe(true);
    v.abgerissen();
    const lang = v.noetig;
    expect(lang).toBeGreaterThan(1.5);
    v.beginnen();
    v.beenden();
    expect(v.noetig).toBeLessThan(lang);
  });
});
