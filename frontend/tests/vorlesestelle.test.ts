// Vorlesestelle (BF-37): Pause, Anhalten, Schlafuhr und Abriss merken den Satz am Server; zu Ende gelesen ist sie weg
import type { Lesequelle } from "../src/lib/vorlesen/typen";

const ruhe = (n = 10) => new Array(n).fill(0).reduce((p) => p.then(() => new Promise((r) => setTimeout(r, 0))), Promise.resolve());

const SEITEN = ["Eins a. Eins b.", "Zwei a. Zwei b. Zwei c.", "Drei a."];
const quelle: Lesequelle = {
  anzahl: SEITEN.length, name: (e) => `Seite ${e + 1}`, text: async (e) => SEITEN[e],
  markiere: () => {}, fuehre: async () => {}, sichtbar: () => true, kapitelende: async () => null,
};

interface Anfrage {
  weg: string;
  art: string;
  inhalt: Record<string, unknown> | null;
}

// Die Stimme des Geräts, nachgestellt: jeder Satz endet erst, wenn der Test es sagt
let gesprochen: { text: string; onend: (() => void) | null }[] = [];
class Aeusserung {
  onend: (() => void) | null = null;
  onboundary = null;
  onerror = null;
  voice = null;
  lang = "";
  rate = 1;
  constructor(public text: string) {}
}

async function frisch(gemerkt: unknown = null) {
  vi.resetModules();
  gesprochen = [];
  const anfragen: Anfrage[] = [];
  vi.stubGlobal("fetch", vi.fn(async (weg: string, init?: RequestInit) => {
    anfragen.push({ weg, art: init?.method ?? "GET", inhalt: typeof init?.body === "string" ? JSON.parse(init.body) : null });
    if ((init?.method ?? "GET") === "GET") return new Response(JSON.stringify(gemerkt));
    if (init?.method === "DELETE") return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ ...JSON.parse(String(init?.body)), gemerkt_am: "2026-11-26T03:00:00Z" }));
  }));
  vi.stubGlobal("SpeechSynthesisUtterance", Aeusserung);
  vi.stubGlobal("speechSynthesis", {
    getVoices: () => [{ voiceURI: "de-1", name: "Gerät", lang: "de-DE" }], addEventListener: () => {}, cancel: () => {},
    speak: (a: Aeusserung) => gesprochen.push(a),
  });
  const { anschluesse } = await import("../src/lib/stand/anschluesse.svelte");
  anschluesse.jetzt = { ...anschluesse.jetzt, vorlesen: false };
  const { vorlesen } = await import("../src/lib/stand/vorlesen.svelte");
  vorlesen.pruefe();
  return { vorlesen, anfragen };
}

const geschrieben = (anfragen: Anfrage[]) => anfragen.filter((a) => a.art !== "GET");
const sprichZuEnde = async () => {
  await ruhe();
  gesprochen.at(-1)?.onend?.();
  await ruhe();
};

describe("Vorlesestelle", () => {
  it("merkt bei Pause und Anhalten den Satz, der gerade klingt, mit Umfang und Ort", async () => {
    const { vorlesen, anfragen } = await frisch();
    vorlesen.liesBuch(quelle, { von: { einheit: 1, zeichen: 0 }, bis: { einheit: 2, zeichen: 0 } }, "Diese Seite", undefined, 7);
    await sprichZuEnde();
    await ruhe();
    expect(gesprochen.at(-1)?.text).toBe("Zwei b.");
    vorlesen.pausiere();
    expect(geschrieben(anfragen).at(-1)).toEqual({ weg: "/api/books/7/vorlesestelle", art: "PUT", inhalt: { einheit: 1, zeichen: 8, bis_einheit: 2, bis_zeichen: 0, umfang: "Diese Seite", ort: "Seite 2" } });
    expect(vorlesen.gemerkt?.stelle?.zeichen).toBe(8);
    vorlesen.halt();
    expect(geschrieben(anfragen).at(-1)?.inhalt?.zeichen).toBe(8);
    expect(vorlesen.aktiv).toBe(false);
  });

  it("löscht die Stelle, wenn der gewählte Umfang zu Ende gelesen ist", async () => {
    const { vorlesen, anfragen } = await frisch();
    vorlesen.liesBuch(quelle, { von: { einheit: 2, zeichen: 0 }, bis: null }, "Ab hier", undefined, 7);
    await sprichZuEnde();
    await ruhe();
    expect(geschrieben(anfragen).at(-1)).toEqual({ weg: "/api/books/7/vorlesestelle", art: "DELETE", inhalt: null });
    expect(vorlesen.gemerkt).toEqual({ buch: 7, stelle: null });
  });

  it("merkt nichts bei einem einzelnen Text (Auswahl, Probe)", async () => {
    const { vorlesen, anfragen } = await frisch();
    vorlesen.lies("Ein Satz. Noch einer.", "Auswahl");
    await ruhe();
    vorlesen.pausiere();
    vorlesen.halt();
    expect(geschrieben(anfragen)).toEqual([]);
  });

  it("kennt die Stelle, die ein anderes Gerät gemerkt hat", async () => {
    const stelle = { einheit: 1, zeichen: 8, bis_einheit: null, bis_zeichen: null, umfang: "Ab hier", ort: "Seite 2", gemerkt_am: "2026-11-26T03:00:00Z" };
    const { vorlesen, anfragen } = await frisch(stelle);
    await vorlesen.ladeStelle(7);
    expect(anfragen.at(-1)?.weg).toBe("/api/books/7/vorlesestelle");
    expect(vorlesen.gemerkt).toEqual({ buch: 7, stelle });
  });
});
