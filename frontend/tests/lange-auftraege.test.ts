// BF-104: lange Aufträge des Servers (Prüfung, Volltexte neu lesen) stehen in der Liste der Aufträge, solange sie nicht fertig
// sind, mit Fortschritt; angehalten oder mit Fehler lassen sie sich fortsetzen.
import type { Faehigkeit, Ich } from "../src/lib/api/familie";
import { auftraege } from "../src/lib/stand/auftraege.svelte";
import { ich } from "../src/lib/stand/ich.svelte";

const stand = (art: string, was: string, s: string, fertig: number, gesamt: number) =>
  ({ art, was, stand: s, gesamt, fertig, teile: [], aktuell: "", grund: "", begonnen: null, geaendert: null, fertig_am: null });

function server(lange: unknown[]) {
  const f = vi.fn((weg: string, init?: RequestInit) => {
    const pfad = String(weg).split("?")[0];
    const daten = pfad === "/api/einrichtung/auftraege" ? lange : pfad.startsWith("/api/einrichtung/auftraege/") ? lange[0] : {};
    return Promise.resolve(new Response(JSON.stringify(daten), { status: 200, headers: { "content-type": "application/json" } }));
  });
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

function ichMit(faehigkeiten: Faehigkeit[]): Ich {
  return {
    profil: { id: "p-1", name: "Malve", zeichen: "feather", farbe: "#6366f1", rolle: "verwaltung", stufe: null, hat_pin: false, hat_bild_pin: false },
    faehigkeiten, darstellung: {}, lesehilfen: null, einblick: [], katze: { an: false, name: "", schnurren: false },
    lesezeit: { an: false, heute_s: 0, grenze_s: null, rest_s: null, ruht: false, ruhe_bis: null, hinweis_ab_s: null },
  } as unknown as Ich;
}

afterEach(() => {
  auftraege.halte();
  auftraege.eigene = [];
  ich.setze(null);
});

describe("Lange Aufträge in der Liste (BF-104)", () => {
  it("zeigt laufende und angehaltene, fertige nicht", async () => {
    ich.setze(ichMit(["einstellungen"]));
    server([stand("ligaturen", "Volltexte mit falschen Ligaturen neu lesen", "laeuft", 30, 120), stand("pruefung", "Originale prüfen", "fertig", 5, 5),
            stand("kopieren", "Originale kopieren", "pause", 2, 8), stand("nachfuehren", "Persönliches nachführen", "laeuft", 1, 3)]);
    await auftraege.auffrischen();
    const eigene = auftraege.alleEigenen.map((a) => [a.titel, a.laeuft, a.pausiert, a.anteil]);
    expect(eigene).toEqual([["Volltexte mit falschen Ligaturen neu lesen", true, false, 0.25], ["Originale kopieren", false, true, 0.25]]);
  });

  it("setzt einen angehaltenen fort", async () => {
    ich.setze(ichMit(["einstellungen"]));
    const f = server([stand("ligaturen", "Volltexte mit falschen Ligaturen neu lesen", "pause", 3, 9)]);
    await auftraege.auffrischen();
    auftraege.alleEigenen[0].fortsetzen!();
    await new Promise((r) => setTimeout(r, 0));
    expect(f.mock.calls.some(([weg, init]) => String(weg).endsWith("/api/einrichtung/auftraege/ligaturen/fortsetzen") && (init as RequestInit)?.method === "POST")).toBe(true);
  });

  it("fragt ohne Einstellungen nicht", async () => {
    ich.setze(ichMit(["lesen"]));
    const f = server([]);
    await auftraege.auffrischen();
    expect(f.mock.calls.map(([weg]) => String(weg).split("?")[0])).not.toContain("/api/einrichtung/auftraege");
  });
});
