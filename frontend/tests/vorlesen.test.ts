import { beforeEach, describe, expect, it, vi } from "vitest";
import { saetze } from "../src/lib/vorlesen/saetze";
import { zeilenAus } from "../src/lib/vorlesen/zeilen";
import { Vorlauf } from "../src/lib/vorlesen/vorlauf";

const antwort = { da: true, hinweis: "", stimmen: [{ id: "anna", name: "Anna", gruppe: "eigene" }, { id: "katalog:b", name: "Bert", gruppe: "eingebaut" }] };

async function frisch(dienst: unknown, angeschlossen = true) {
  vi.resetModules();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(dienst))));
  vi.stubGlobal("speechSynthesis", { getVoices: () => [{ voiceURI: "de-1", name: "Gerät", lang: "de-DE" }], addEventListener: () => {}, cancel: () => {} });
  const { anschluesse } = await import("../src/lib/stand/anschluesse.svelte");
  anschluesse.jetzt = { ...anschluesse.jetzt, vorlesen: angeschlossen };
  const { vorlesen } = await import("../src/lib/stand/vorlesen.svelte");
  vorlesen.pruefe();
  await new Promise((r) => setTimeout(r, 5));
  return vorlesen;
}

beforeEach(() => localStorage.clear());

describe("Stimmenauswahl", () => {
  it("bietet die Stimmen des Sprechdienstes in Gruppen, zuerst die Vorgabe", async () => {
    const v = await frisch(antwort);
    expect(v.stimme).toBe("dienst:");
    expect(v.gruppen.map(([g]) => g)).toEqual(["Sprechdienst", "Eigene Stimmen", "Eingebaute Stimmen"]);
  });
  it("merkt sich die Wahl auf dem Gerät", async () => {
    (await frisch(antwort)).waehle("dienst:anna");
    expect((await frisch(antwort)).stimme).toBe("dienst:anna");
  });
  it("schweigt der Sprechdienst, springt keine andere Stimme ein", async () => {
    expect((await frisch({ da: false, stimmen: [], hinweis: "Der Sprechdienst antwortet nicht" })).stimmen).toEqual([]);
  });
  it("liest auch dort, wo vorher niemand die Stimmen erfragt hat (Auswahl im Text)", async () => {
    vi.resetModules();
    const gesprochen: string[] = [];
    vi.stubGlobal("speechSynthesis", { getVoices: () => [{ voiceURI: "de-1", name: "Gerät", lang: "de-DE" }], addEventListener: () => {}, cancel: () => {}, speak: (a: { text: string }) => gesprochen.push(a.text) });
    vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} });
    const { anschluesse } = await import("../src/lib/stand/anschluesse.svelte");
    anschluesse.jetzt = { ...anschluesse.jetzt, vorlesen: false };
    const { vorlesen } = await import("../src/lib/stand/vorlesen.svelte");
    vorlesen.lies("Ein Satz aus der Auswahl.", "Auswahl");
    await new Promise((r) => setTimeout(r, 5));
    expect([vorlesen.aktiv, gesprochen]).toEqual([true, ["Ein Satz aus der Auswahl."]]);
    vorlesen.halt();
  });
  it("ohne Sprechdienst gelten die Stimmen des Geräts, eine verschwundene Wahl fällt weg", async () => {
    localStorage.setItem("vorlesen.stimme", "dienst:anna");
    const v = await frisch({}, false);
    expect(v.stimmen.map((s) => s.id)).toEqual(["geraet:de-1"]);
    expect(v.stimme).toBe("geraet:de-1");
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
