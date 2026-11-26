// BF-51: Befunde aus dem Grenztest: lange Listen, Sortierung, Meldungen des Servers, Koppeln, Klassen. Lange Wörter auf
// dem Umschlag prüft jetzt umschlag.test.ts (BF-59)
import { render, screen, waitFor } from "@testing-library/svelte";
import Anmeldung from "../src/ansichten/anmeldung/Anmeldung.svelte";
import { meldungAus } from "../src/lib/api/client";
import { eingrenzen, VIELE } from "../src/lib/eingrenzen";
import { NAMENSFOLGE } from "../src/lib/stand/bestand.svelte";

const stile = import.meta.glob<string>("../src/stil/*.css", { query: "?raw", import: "default", eager: true });

describe("Lange Listen in Leiste und Filterfeld", () => {
  const regale = Array.from({ length: 40 }, (_, n) => ({ id: n, name: n === 39 ? "Übermaß" : `Regal ${n}` }));

  it("bei wenigen bleibt alles, wie es ist", () => {
    const wenige = regale.slice(0, VIELE);
    expect(eingrenzen(wenige, (r) => r.name, "", () => false, 5)).toEqual({ gezeigt: wenige, weitere: 0, mitSuche: false });
  });

  it("bei vielen mit Suche und Grenze; Gewähltes bleibt sichtbar, auch außerhalb der Grenze", () => {
    const e = eingrenzen(regale, (r) => r.name, "", (r) => r.id === 30, 20);
    expect(e.mitSuche).toBe(true);
    expect(e.gezeigt.map((r) => r.id)).toEqual([...Array.from({ length: 20 }, (_, n) => n), 30]);
    expect(e.weitere).toBe(20);
  });

  it("sucht ohne Rücksicht auf Groß und Klein, auch mit Umlauten", () => {
    expect(eingrenzen(regale, (r) => r.name, "übermaß", () => false, 20).gezeigt.map((r) => r.name)).toEqual(["Übermaß"]);
    expect(eingrenzen(regale, (r) => r.name, "regal 3", () => false, 20).gezeigt.length).toBe(10);
  });
});

it("Regale nach Namen, Zahlen als Zahlen", () => {
  expect(["Regal 225", "Regal 25", "Regal 3", "regal 100"].sort(NAMENSFOLGE.compare)).toEqual(["Regal 3", "Regal 25", "regal 100", "Regal 225"]);
});

describe("Meldungen des Servers", () => {
  it("nimmt einen Satz, die Liste der Prüffehler und einzelne Einträge", () => {
    expect(meldungAus("Name zu lang")).toBe("Name zu lang");
    expect(meldungAus([{ type: "string_too_long", loc: ["body", "name"], msg: "Höchstens 50 Zeichen" }, { msg: "Höchstens 50 Zeichen" }, { msg: "Farbe fehlt" }])).toBe("Höchstens 50 Zeichen; Farbe fehlt");
    expect(meldungAus({ msg: "Fehlt" })).toBe("Fehlt");
    expect(meldungAus(undefined)).toBe("");
    expect(meldungAus([{ loc: ["x"] }])).toBe("");
  });
});

describe("Koppeln-Link", () => {
  function app(angaben: Record<string, unknown>) {
    globalThis.fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(angaben)))) as unknown as typeof fetch;
  }

  it("ohne Kellerwolke zeigt der Link die Anmeldung unter dem Namen der App", async () => {
    app({ name: "BücherFreunde", art: "eigen", kellerwolke: "", besitzer: null, eingerichtet: true });
    location.hash = "#koppeln=AB12-CD34";
    render(Anmeldung, { props: { onerfolg: () => {} } });
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("BücherFreunde"));
    expect(document.querySelector('input[type="password"]')).not.toBe(null);
  });

  it("mit Kellerwolke koppelt er", async () => {
    app({ name: "BücherFreunde", art: "kellerwolke", kellerwolke: "https://wolke.lan", besitzer: null, eingerichtet: true });
    location.hash = "#koppeln=AB12-CD34";
    render(Anmeldung, { props: { onerfolg: () => {} } });
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Gerät koppeln"));
  });
});

it("die Ablage beim Ziehen trifft keine allgemeine Klasse .ueber aus den Stilen", () => {
  const regeln = Object.values(stile).join("\n").replace(/\/\*[\s\S]*?\*\//g, "");
  expect(regeln).not.toMatch(/(^|[\s,}])\.ueber(?![\w-])/m);
});
