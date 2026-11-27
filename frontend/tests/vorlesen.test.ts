import { beforeEach, describe, expect, it, vi } from "vitest";
import { saetze } from "../src/lib/vorlesen/saetze";
import { zeilenAus } from "../src/lib/vorlesen/zeilen";
import { MINDESTENS_S, Vorlauf } from "../src/lib/vorlesen/vorlauf";

const PRIVAT = "5b1e7c3a-2f4d-4a6b-8c9d-0e1f2a3b4c5d";
const FREI = [{ bereich: "privat", frei: true, hinweis: "" }, { bereich: "fremd", frei: true, hinweis: "" }, { bereich: "katalog", frei: true, hinweis: "" }];
const antwort = {
  da: true, hinweis: "", bereiche: FREI,
  stimmen: [{ id: PRIVAT, name: "Probestimme privat", bereich: "privat", sprache: "de" }, { id: "katalog:serena", name: "serena", bereich: "katalog", sprache: null }],
};
const erwachsen = (stimme = "") => ({ profil: { id: "p-1", name: "Wiebke", rolle: "verwaltung" }, faehigkeiten: [], vorlesen: { stimme, werte: {}, eigene_wahl: true } });
const kind = (stimme = "") => ({ profil: { id: "k-1", name: "Joris", rolle: "kind" }, faehigkeiten: [], vorlesen: { stimme, werte: {}, eigene_wahl: false } });

async function frisch(dienst: unknown, { angeschlossen = true, profil = null as unknown } = {}) {
  vi.resetModules();
  const gesendet: [string, RequestInit][] = [];
  vi.stubGlobal("fetch", vi.fn(async (weg: string, optionen: RequestInit = {}) => {
    gesendet.push([weg, optionen]);
    if (weg.includes("/api/familie/ich/vorlesen")) return new Response(JSON.stringify({ stimme: JSON.parse(String(optionen.body)).stimme, werte: {}, eigene_wahl: true }));
    return new Response(JSON.stringify(dienst));
  }));
  vi.stubGlobal("speechSynthesis", { getVoices: () => [{ voiceURI: "de-1", name: "Gerät", lang: "de-DE" }], addEventListener: () => {}, cancel: () => {} });
  const { anschluesse } = await import("../src/lib/stand/anschluesse.svelte");
  anschluesse.jetzt = { ...anschluesse.jetzt, vorlesen: angeschlossen };
  const { ich } = await import("../src/lib/stand/ich.svelte");
  ich.setze(profil as Parameters<typeof ich.setze>[0]);
  const { vorlesen } = await import("../src/lib/stand/vorlesen.svelte");
  vorlesen.pruefe();
  await new Promise((r) => setTimeout(r, 5));
  const gespeichert = () => gesendet.filter(([weg]) => weg.includes("/api/familie/ich/vorlesen")).map(([, o]) => [o.method, JSON.parse(String(o.body))]);
  return { v: vorlesen, ich, gespeichert };
}

beforeEach(() => localStorage.clear());

describe("Stimmenauswahl", () => {
  it("bietet die Stimmen der Vertonung in Gruppen nach ihren Bereichen, zuerst die Stimme ab Werk, dazu die des Geräts", async () => {
    const { v } = await frisch(antwort, { profil: erwachsen() });
    expect(v.stimme).toBe("dienst:");
    expect(v.gruppen.map(([g]) => g)).toEqual(["Vertonung", "Private Stimmen", "Eingebaute Stimmen", "Dieses Gerät"]);
    expect(v.freigabe).toBe("");
  });
  it("nennt ohne Freigabe privater Stimmen den Grund und den Weg dorthin", async () => {
    const hinweis = "Private Stimmen sind dieser App nicht erlaubt. Freigabe in der Vertonung unter Private Stimmen für";
    const ohne = { ...antwort, stimmen: antwort.stimmen.slice(1), bereiche: [{ bereich: "privat", frei: false, hinweis }, ...FREI.slice(1)] };
    const { v } = await frisch(ohne, { profil: erwachsen() });
    expect(v.freigabe).toBe(hinweis);
    expect(v.gruppen.map(([g]) => g)).toEqual(["Vertonung", "Eingebaute Stimmen", "Dieses Gerät"]);
  });
  it("merkt sich die Wahl im Profil, nicht im Browser", async () => {
    const { v, ich, gespeichert } = await frisch(antwort, { profil: erwachsen() });
    v.waehle("dienst:katalog:serena");
    await new Promise((r) => setTimeout(r, 5));
    expect(gespeichert()).toEqual([["PATCH", { stimme: "katalog:serena" }]]);
    expect([ich.jetzt?.vorlesen.stimme, localStorage.getItem("vorlesen.stimme")]).toEqual(["katalog:serena", null]);
    expect((await frisch(antwort, { profil: erwachsen("katalog:serena") })).v.stimme).toBe("dienst:katalog:serena");
  });
  it("übernimmt die frühere Wahl dieses Browsers einmal ins Profil", async () => {
    localStorage.setItem("vorlesen.stimme", "dienst:katalog:serena");
    const { v, gespeichert } = await frisch(antwort, { profil: erwachsen() });
    expect([v.stimme, gespeichert(), localStorage.getItem("vorlesen.stimme")]).toEqual(["dienst:katalog:serena", [["PATCH", { stimme: "katalog:serena" }]], null]);
  });
  it("schweigt die Vertonung, springt keine Stimme des Geräts still ein", async () => {
    const { v } = await frisch({ da: false, stimmen: [], bereiche: [], hinweis: "Die Vertonung ist gerade nicht erreichbar" }, { profil: erwachsen("katalog:serena") });
    expect([v.stimme, v.bereit, v.hinweis]).toEqual(["", false, "Die Vertonung ist gerade nicht erreichbar"]);
    expect(v.stimmen.map((s) => s.id)).toEqual(["geraet:de-1"]);                           // als ausdrückliche Wahl
  });
  it("die Stimme des Geräts gilt, wenn sie gewählt ist; ein Kind hört die Wahl der Eltern und speichert nichts", async () => {
    expect((await frisch(antwort, { profil: erwachsen("geraet:de-1") })).v.stimme).toBe("geraet:de-1");
    const { v, gespeichert } = await frisch(antwort, { profil: kind("geraet") });
    expect(v.stimme).toBe("geraet:de-1");
    v.waehle("dienst:katalog:serena");
    expect([v.stimme, gespeichert()]).toEqual(["dienst:katalog:serena", []]);
    expect((await frisch(antwort, { profil: kind("katalog:serena") })).v.stimme).toBe("dienst:katalog:serena");
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
  it("ohne Vertonung gelten die Stimmen des Geräts, eine verschwundene Wahl fällt weg", async () => {
    const { v } = await frisch({}, { angeschlossen: false, profil: erwachsen("katalog:serena") });
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
    expect([v.genug(MINDESTENS_S - 0.5, false), v.genug(MINDESTENS_S, false)]).toEqual([false, true]);   // kleiner Vorlauf (BF-106)
    v.abgerissen();
    const lang = v.noetig;
    expect(lang).toBeGreaterThan(MINDESTENS_S);
    v.beginnen();
    v.beenden();
    expect(v.noetig).toBeLessThan(lang);
  });
});

describe("Probe (BF-101)", () => {
  it("scheitert die Probe, endet sie mit Meldung, und die Probe-Taste ist wieder frei", async () => {
    vi.resetModules();
    vi.stubGlobal("Audio", class { src = ""; play = () => Promise.resolve(); pause() {} });
    vi.stubGlobal("speechSynthesis", { getVoices: () => [], addEventListener: () => {}, cancel: () => {} });
    vi.stubGlobal("fetch", vi.fn(async (weg: string) => {
      if (weg === "/api/vorlesen") return new Response('{"art": "fehler", "meldung": "Die Vertonung ist gerade belegt"}\n');
      return new Response(JSON.stringify(antwort));
    }));
    const { anschluesse } = await import("../src/lib/stand/anschluesse.svelte");
    anschluesse.jetzt = { ...anschluesse.jetzt, vorlesen: true };
    const { melde } = await import("../src/lib/stand/meldungen.svelte");
    const warn = vi.spyOn(melde, "warn");
    const { vorlesen, PROBE_WAS } = await import("../src/lib/stand/vorlesen.svelte");
    vorlesen.pruefe();
    await new Promise((r) => setTimeout(r, 5));
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vorlesen.probe();
    expect([vorlesen.aktiv, vorlesen.was]).toEqual([true, PROBE_WAS]);
    await vi.advanceTimersByTimeAsync(120_000);                  // der Zulauf fragt erst einige Male erneut
    vi.useRealTimers();
    expect(vorlesen.aktiv).toBe(false);
    expect(warn).toHaveBeenCalledWith("Die Vertonung ist gerade belegt. Bitte erneut versuchen.");
  });
});
