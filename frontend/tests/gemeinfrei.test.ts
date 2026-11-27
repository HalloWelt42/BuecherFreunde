// BF-98: Gemeinfreie Bücher mit eigenem Katalog. Texte nach dem Entwurf, Vorschläge beim Tippen erst nach der Pause und nur aus
// dem Katalog, "Bei Gutendex suchen" sichtbar wartend und abbrechbar, Störung als Meldung mit den Treffern aus dem Katalog, der
// Katalog als Auftrag beim ersten Öffnen, die Lücke mit "In die Lücke holen" und "Bei Gemeinfreie Bücher zeigen", Fehler nie als
// bloße Nummer. Alle Titel und Namen sind erfunden.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Gemeinfreie from "../src/ansichten/hinzu/quellen/Gemeinfreie.svelte";
import Lueckenfeld from "../src/ansichten/sammlung/Lueckenfeld.svelte";
import { Lueckenstand } from "../src/ansichten/sammlung/lueckenstand.svelte";
import { ApiError } from "../src/lib/api/client";
import type { Faehigkeit, Ich } from "../src/lib/api/familie";
import type { Fundbuch, Fundliste, Katalogstand } from "../src/lib/api/gutenberg";
import type { Luecke, Reihe } from "../src/lib/api/luecken";
import { dauer, groesseVon, zeitspanne } from "../src/lib/format";
import { auftraege } from "../src/lib/stand/auftraege.svelte";
import { erneuernText, gutenberg, katalogauftrag, katalogzeile, VERZOEGERUNG_MS, wartehinweis } from "../src/lib/stand/gutenberg.svelte";
import { ich } from "../src/lib/stand/ich.svelte";
import { fehlertext, melde } from "../src/lib/stand/meldungen.svelte";

const darf = (...faehigkeiten: Faehigkeit[]) => ich.setze({ profil: { id: "p-1", name: "Malve", rolle: "erwachsen" }, faehigkeiten } as unknown as Ich);

const fund = (gutenberg_id: number, titel: string, autor = "Marks, Jonte"): Fundbuch => ({
  gutenberg_id, titel, autor, sprachen: ["de"], download_url: `https://gutenberg.pglaf.org/cache/epub/${gutenberg_id}/pg${gutenberg_id}-images-3.epub`, download_format: "epub",
  cover_url: `https://gutenberg.pglaf.org/cache/epub/${gutenberg_id}/pg${gutenberg_id}.cover.medium.jpg`, download_count: 0,
});
const KAIWIND = [fund(102, "Kaiwind: Erster Teil"), fund(103, "Kaiwind: Zweiter Teil")];
const liste = (buecher: Fundbuch[], ueber: Partial<Fundliste> = {}): Fundliste => ({ gesamt: buecher.length, seite: 1, naechste: null, vorherige: null, buecher, herkunft: "katalog", hinweis: "", ...ueber });
const stand = (ueber: Partial<Katalogstand> = {}): Katalogstand => ({
  da: true, anzahl: 76012, stand: "2026-11-08", geholt_am: "2026-11-20T03:00:00Z", alter_tage: 2, faellig: false, erneuern_tage: 7, laeuft: false, schritt: "", erledigt: 0, gesamt: null,
  grund: "", suche_geduld_s: 120, ...ueber,
});
const STOERUNG = "Gutendex antwortet gerade nicht, der Dienst ist überlastet. Die Treffer kommen aus dem eigenen Katalog; später erneut versuchen.";

type Weg = (url: URL, o?: RequestInit) => unknown;

/** Antworten je Weg; was keiner kennt, antwortet leer wie beim Server */
function server(wege: Record<string, Weg>) {
  const f = vi.fn(async (adresse: string, o?: RequestInit) => {
    const url = new URL(adresse, "http://x");
    const weg = wege[`${o?.method ?? "GET"} ${url.pathname}`] ?? wege[url.pathname];
    const daten = weg ? await weg(url, o) : url.pathname === "/api/annahme" ? { eintraege: [], zaehler: {}, quellen: {}, vorschauen: [] } : {};
    return daten instanceof Response ? daten : new Response(JSON.stringify(daten), { status: 200 });
  });
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

const aufrufe = (f: ReturnType<typeof server>, pfad: string) => f.mock.calls.filter(([a]) => new URL(a, "http://x").pathname === pfad);

function zuruecksetzen() {
  gutenberg.abbrechen();
  gutenberg.wort = "";
  gutenberg.sprache = "de";
  gutenberg.leere();
  gutenberg.katalog = null;
}

beforeEach(() => zuruecksetzen());
afterEach(() => {
  vi.useRealTimers();
  ich.setze(null);
});

describe("Texte nach dem Entwurf", () => {
  it("nennt Katalog, Fortschritt in Byte, Warten und Erneuern in Klartext", () => {
    expect(katalogzeile(stand())).toBe("Eigener Katalog: 76.012 Bücher, Stand 08.11.2026, wird wöchentlich erneuert");
    expect(katalogzeile(stand({ da: false, grund: "Der Spiegel des Project Gutenberg ist gerade nicht erreichbar" }))).toBe("Eigener Katalog fehlt noch: Der Spiegel des Project Gutenberg ist gerade nicht erreichbar");
    const a = katalogauftrag(stand({ da: false, laeuft: true, schritt: "holen", erledigt: 12_400_000, gesamt: 21_300_000 }));
    expect([a.titel, a.text, a.anteil?.toFixed(2)]).toEqual(["Eigener Katalog wird geholt", "12,4 von 21,3 MB", "0.58"]);
    expect(katalogauftrag(stand({ laeuft: true, schritt: "bauen", erledigt: 5, gesamt: 10 })).titel).toBe("Eigener Katalog wird erneuert");
    expect(katalogauftrag(stand({ da: false, laeuft: true, schritt: "holen" })).anteil).toBeNull();
    expect(wartehinweis(120, true)).toBe("Der Suchdienst ist oft langsam. Die App wartet bis zu 2 Minuten; die Vorschläge unten kannst du schon holen.");
    expect(wartehinweis(45, false)).toBe("Der Suchdienst ist oft langsam. Die App wartet bis zu 45 Sekunden.");
    expect([dauer(23), dauer(125), dauer(3723), zeitspanne(120), erneuernText(1), erneuernText(10)]).toEqual(["0:23", "2:05", "1:02:03", "2 Minuten", "täglich", "alle 10 Tage"]);
    expect(groesseVon(600, 21_300_000)).toBe("0,0 von 21,3 MB");
  });

  it("zeigt einen Fehler ohne Satz des Servers nie als bloße Nummer", () => {
    for (const status of [500, 502, 503, 404, 403, 400]) expect(fehlertext(new ApiError(status, `HTTP ${status}`))).not.toMatch(/\d/);
    expect(fehlertext(new ApiError(502, STOERUNG))).toBe(STOERUNG);
  });
});

describe("Vorschläge und Suche", () => {
  it("fragt beim Tippen erst nach der Pause und nur den eigenen Katalog", async () => {
    vi.useFakeTimers();
    const f = server({ "/api/gutenberg/vorschlaege": () => liste(KAIWIND) });
    gutenberg.wort = "kai";
    gutenberg.tippe();
    gutenberg.wort = "kaiw";
    gutenberg.tippe();
    await vi.advanceTimersByTimeAsync(VERZOEGERUNG_MS - 1);
    expect(aufrufe(f, "/api/gutenberg/vorschlaege")).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1);
    const [[adresse]] = aufrufe(f, "/api/gutenberg/vorschlaege");
    expect(new URL(adresse, "http://x").searchParams.get("q")).toBe("kaiw");
    await vi.advanceTimersByTimeAsync(0);
    expect(gutenberg.treffer.map((b) => b.gutenberg_id)).toEqual([102, 103]);
    expect(gutenberg.herkunft).toBe("katalog");
    expect(aufrufe(f, "/api/gutenberg/suche")).toHaveLength(0);
  });

  it("wartet sichtbar auf Gutendex, lässt die Auswahl stehen und bricht auf Wunsch ab", async () => {
    vi.useFakeTimers();
    const warnt = vi.spyOn(melde, "warn");
    server({
      "/api/gutenberg/katalog": () => stand(),
      "/api/gutenberg/vorschlaege": () => liste(KAIWIND),
      "/api/gutenberg/suche": (_u, o) => new Promise((_, nein) => o?.signal?.addEventListener("abort", () => nein(new DOMException("abgebrochen", "AbortError")))),
    });
    gutenberg.wort = "kaiwind";
    await gutenberg.vorschlagen();
    gutenberg.schalte(gutenberg.treffer[0]);
    render(Gemeinfreie);
    await vi.advanceTimersByTimeAsync(0);
    expect(screen.getByText("Eigener Katalog: 76.012 Bücher, Stand 08.11.2026, wird wöchentlich erneuert")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "Bei Gutendex suchen" }));
    await vi.advanceTimersByTimeAsync(23_000);
    expect(screen.getByText("Gutendex wird gefragt")).toBeTruthy();
    expect(screen.getByText("seit 0:23")).toBeTruthy();
    expect(screen.getByText("Der Suchdienst ist oft langsam. Die App wartet bis zu 2 Minuten; die Vorschläge unten kannst du schon holen.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Bei Gutendex suchen" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "1 Buch holen" })).toBeTruthy();
    expect(screen.getByText("aus dem eigenen Katalog")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));
    await vi.advanceTimersByTimeAsync(0);
    expect(gutenberg.fragt).toBe(false);
    expect(screen.queryByText("Gutendex wird gefragt")).toBeNull();
    expect(gutenberg.zahl).toBe(1);
    expect(warnt).not.toHaveBeenCalled();
    warnt.mockRestore();
  });

  it("zeigt bei gestörtem Gutendex die Treffer aus dem Katalog mit Meldung in Klartext", async () => {
    const warnt = vi.spyOn(melde, "warn");
    server({ "/api/gutenberg/katalog": () => stand(), "/api/gutenberg/suche": () => liste([KAIWIND[1]], { hinweis: STOERUNG }) });
    gutenberg.wort = "kaiwind zweiter";
    render(Gemeinfreie);
    await gutenberg.suche();
    expect(warnt).toHaveBeenCalledWith(STOERUNG);
    expect(await screen.findByText("aus dem eigenen Katalog, Gutendex gerade gestört")).toBeTruthy();
    expect(screen.getByText("Kaiwind: Zweiter Teil")).toBeTruthy();
    warnt.mockRestore();
  });

  it("meldet einen Ausfall ohne Katalog mit dem Satz des Servers", async () => {
    const warnt = vi.spyOn(melde, "warn");
    const satz = "Gutendex antwortet gerade nicht, der Dienst ist überlastet. Später erneut versuchen.";
    server({ "/api/gutenberg/suche": () => new Response(JSON.stringify({ detail: satz }), { status: 502 }) });
    await gutenberg.suche();
    expect(warnt).toHaveBeenCalledWith(satz);
    server({ "/api/gutenberg/suche": () => new Response("<html>Bad Gateway</html>", { status: 502 }) });
    await gutenberg.suche();
    expect(warnt.mock.calls.at(-1)?.[0]).not.toMatch(/\d/);
    warnt.mockRestore();
  });

  it("holt beim ersten Öffnen ohne Katalog ihn einmal von selbst, als Auftrag mit Fortschritt", async () => {
    vi.useFakeTimers();
    const gut = vi.spyOn(melde, "gut");
    let lage: "leer" | "laeuft" | "fertig" = "leer";
    const f = server({
      "GET /api/gutenberg/katalog": () => ({ leer: stand({ da: false }), laeuft: stand({ da: false, laeuft: true, schritt: "holen", erledigt: 12_400_000, gesamt: 21_300_000 }), fertig: stand() })[lage],
      "POST /api/gutenberg/katalog": () => {
        lage = "laeuft";
        return stand({ da: false, laeuft: true, schritt: "holen", erledigt: 0, gesamt: 21_300_000 });
      },
    });
    render(Gemeinfreie);
    await vi.advanceTimersByTimeAsync(0);
    expect(f.mock.calls.filter(([, o]) => o?.method === "POST")).toHaveLength(1);
    expect(screen.getByText("Eigener Katalog wird geholt")).toBeTruthy();
    expect(screen.getByText("0,0 von 21,3 MB")).toBeTruthy();
    expect(screen.getByText('Einmal, danach wöchentlich, vom Spiegel des Project Gutenberg. Bis er da ist, sucht "Bei Gutendex suchen" wie bisher.')).toBeTruthy();
    await vi.advanceTimersByTimeAsync(1000);
    expect(screen.getByText("12,4 von 21,3 MB")).toBeTruthy();
    expect(auftraege.eigene.find((a) => a.id === "gutenberg-katalog")).toMatchObject({ titel: "Eigenen Katalog holen", laeuft: true, text: "12,4 von 21,3 MB" });
    lage = "fertig";
    await vi.advanceTimersByTimeAsync(1000);
    expect(gut).toHaveBeenCalledWith("Eigener Katalog ist da: 76.012 Bücher");
    expect(auftraege.eigene.find((a) => a.id === "gutenberg-katalog")).toMatchObject({ laeuft: false, text: "Fertig, 76.012 Bücher" });
    expect(screen.getByRole("button", { name: "Jetzt erneuern" })).toBeTruthy();
    await gutenberg.oeffneKatalog();
    expect(f.mock.calls.filter(([, o]) => o?.method === "POST")).toHaveLength(1);              // von selbst nur einmal
    gut.mockRestore();
  });
});

describe("Fehlender Band, gemeinfrei zu haben", () => {
  const reihe = { sprache: "de", name: "Deutsch", reihe: "Kaiwind" } as Reihe;
  const luecke = (ueber: Partial<Luecke> = {}): Luecke => ({
    sprache: "de", nummer: 2, titel: "Kaiwind. Zweiter Teil", autor: "Jonte Marks", isbn: "", jahr: null, quelle: "dnb", kopieren: "Kaiwind. Zweiter Teil, Jonte Marks", suchadresse: null,
    gemeinfrei: KAIWIND[1], ...ueber,
  });

  it("bietet Holen und Zeigen nur mit Hinzufügen", () => {
    darf("lesen", "luecken");
    const ohne = render(Lueckenfeld, { luecke: luecke(), reihe, stand: new Lueckenstand(3), autor: "", onschliessen: () => {} });
    expect(screen.queryByText("Gemeinfrei zu haben")).toBeNull();
    ohne.unmount();
    darf("lesen", "luecken", "hinzufuegen");
    render(Lueckenfeld, { luecke: luecke({ gemeinfrei: null }), reihe, stand: new Lueckenstand(3), autor: "", onschliessen: () => {} });
    expect(screen.queryByText("Gemeinfrei zu haben")).toBeNull();
  });

  it("holt in die Lücke über die Vorschau mit Sammlung, Band und Sprache", async () => {
    darf("lesen", "luecken", "hinzufuegen");
    const f = server({ "POST /api/gutenberg/luecke": () => ({ vorschau: "v-9" }) });
    const zu = vi.fn();
    render(Lueckenfeld, { luecke: luecke(), reihe, stand: new Lueckenstand(3), autor: "", onschliessen: zu });
    expect(screen.getByText("Gemeinfrei zu haben")).toBeTruthy();
    expect(screen.getByText("Im eigenen Katalog des Project Gutenberg: EPUB, Deutsch")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "In die Lücke holen" }));
    await vi.waitFor(() => expect(location.pathname).toBe("/import/vorschau/v-9"));
    const [, o] = f.mock.calls.find(([a]) => a === "/api/gutenberg/luecke")!;
    const { gutenberg_id, titel, autor, download_url, download_format, cover_url } = KAIWIND[1];
    expect(JSON.parse(String(o?.body))).toEqual({ buch: { gutenberg_id, titel, autor, download_url, download_format, cover_url }, sammlung_id: 3, band: "2", sprache: "de" });
    expect(zu).toHaveBeenCalled();
  });

  it("zeigt bei den gemeinfreien Büchern mit gefüllter Suche", async () => {
    darf("lesen", "luecken", "hinzufuegen");
    const f = server({ "/api/gutenberg/vorschlaege": () => liste([KAIWIND[1]]) });
    render(Lueckenfeld, { luecke: luecke(), reihe, stand: new Lueckenstand(3), autor: "", onschliessen: () => {} });
    await fireEvent.click(screen.getByRole("button", { name: "Bei Gemeinfreie Bücher zeigen" }));
    expect(location.pathname).toBe("/import");
    expect([gutenberg.wort, gutenberg.sprache, gutenberg.zeigen]).toEqual(["Kaiwind: Zweiter Teil", "de", true]);
    await vi.waitFor(() => expect(aufrufe(f, "/api/gutenberg/vorschlaege")).toHaveLength(1));
    gutenberg.zeigen = false;
  });
});
