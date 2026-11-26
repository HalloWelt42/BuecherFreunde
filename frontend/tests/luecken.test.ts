// BF-75: Lücken in Sammlungen. Zahlen der Reihe, die Zahl der Bände im Formular, Platzhalter in die Suchadresse, das Feld zum
// fehlenden Band, das Regal je Sprache und dass ohne die Fähigkeit nichts davon erscheint. Alle Namen sind erfunden.
import { fireEvent, render, screen } from "@testing-library/svelte";
import Lueckenteil from "../src/ansichten/einstellungen/Lueckenteil.svelte";
import Lueckenfeld from "../src/ansichten/sammlung/Lueckenfeld.svelte";
import Lueckenregal from "../src/ansichten/sammlung/Lueckenregal.svelte";
import { Lueckenstand } from "../src/ansichten/sammlung/lueckenstand.svelte";
import type { Faehigkeit, Ich } from "../src/lib/api/familie";
import type { Luecke, Reihe, Sammlungsluecken } from "../src/lib/api/luecken";
import { einfuegen, gesamtAus, herkunftstext, lueckenvorgabe, reihenzahl } from "../src/lib/luecken";
import { annahme } from "../src/lib/stand/annahme.svelte";
import { ich } from "../src/lib/stand/ich.svelte";
import type { Buch } from "../src/lib/typen";

const darf = (...faehigkeiten: Faehigkeit[]) => ich.setze({ profil: { id: "p-1", name: "Malve", rolle: "erwachsen" }, faehigkeiten } as unknown as Ich);

const nachschlagen = (stand: Reihe["nachschlagen"]["stand"] = "fertig", grund = ""): Reihe["nachschlagen"] => ({ stand, quelle: "dnb", quelle_name: "Verzeichnis 3", reihe: "Kaiwind", grund, am: null });

function reihe(ueber: Partial<Reihe> = {}): Reihe {
  return { sprache: "de", name: "Deutsch", reihe: "Kaiwind", gesamt: 12, herkunft: "quelle", quelle_gesamt: 12, eigene: null, nachschlagen: nachschlagen(), buecher: 8, belegt: 8, fehlen: [4, 9], zeile: "es fehlen 4 und 9", eintraege: [], ...ueber };
}

function luecke(ueber: Partial<Luecke> = {}): Luecke {
  return { sprache: "de", nummer: 4, titel: "Der stille Kai", autor: "Jonte Marks", isbn: "978-3-99999-004-0", jahr: 2019, quelle: "dnb", kopieren: "Der stille Kai, Jonte Marks, Kaiwind Band 4, ISBN 978-3-99999-004-0", suchadresse: "https://katalog.example/suche?q=Der%20stille%20Kai", ...ueber };
}

const buch = (id: number, title: string, band: string) => ({ id, title, author: "Jonte Marks", band_nummer: band, file_format: "epub", categories: [], umschlag: "gestaltet", cover_path: "", reading_position: "", rating: 0 }) as unknown as Buch;

function luecken(ueber: Partial<Sammlungsluecken> = {}): Sammlungsluecken {
  return {
    sammlung_id: 3, name: "Kaiwind", autor: "Jonte Marks", an: true, ausgeblendet: [],
    reihen: [
      reihe({ eintraege: [{ art: "buch", band: "3", nummer: 3, zwischen: false, buch_id: 30, buch: buch(30, "Kaiwind 3: Ebbe", "3"), luecke: null }, { art: "luecke", band: "4", nummer: 4, zwischen: false, buch_id: null, buch: null, luecke: luecke() }] }),
      reihe({ sprache: "en", name: "Englisch", gesamt: null, herkunft: "", quelle_gesamt: null, fehlen: [], zeile: "", buecher: 2, belegt: 2, eintraege: [] }),
    ],
    ...ueber,
  };
}

/** Die Lücken auf ihren Wegen; was der Bestand nach einer Änderung nachlädt, antwortet leer wie beim Server */
function server(antwort: unknown = luecken()) {
  const LISTEN = ["/api/categories", "/api/collections"];
  const f = vi.fn((weg: string, _o?: RequestInit) => {
    const pfad = weg.split("?")[0];
    const daten = LISTEN.includes(pfad) ? [] : pfad === "/api/config/stats" || pfad === "/api/katalog" ? {} : antwort;
    return Promise.resolve(new Response(JSON.stringify(daten), { status: 200 }));
  });
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

afterEach(() => ich.setze(null));

describe("Zahlen der Reihe und der Bände", () => {
  it("nennt belegte von allen Bänden, ohne Zahl die Bände", () => {
    expect(reihenzahl(reihe())).toBe("8 von 12");
    expect(reihenzahl(reihe({ gesamt: null, buecher: 1 }))).toBe("1 Band");
  });

  it("sagt, woher die Zahl kommt", () => {
    expect(herkunftstext(reihe()).text).toBe("aus den Quellen");
    expect(herkunftstext(reihe({ herkunft: "eigene", eigene: 15 })).text).toBe("eigene Angabe, die Quellen nennen 12");
    expect(herkunftstext(reihe({ herkunft: "keine" })).text).toBe("ohne Zahl");
    expect(herkunftstext(reihe({ herkunft: "", quelle_gesamt: null, nachschlagen: nachschlagen("fertig", "Die Quelle kennt die Reihe nicht") })).text).toBe("Die Quelle kennt die Reihe nicht");
    expect(herkunftstext(reihe({ herkunft: "", nachschlagen: nachschlagen("offen") })).text).toBe("wird nachgeschlagen");
  });

  it("macht aus der Eingabe eine eigene Angabe, leer heißt ohne Zahl, Unverändertes bleibt", () => {
    expect(gesamtAus(reihe(), "15")).toEqual({ sprache: "de", wahl: "eigene", zahl: 15 });
    expect(gesamtAus(reihe(), "12")).toBeNull();
    expect(gesamtAus(reihe(), "")).toEqual({ sprache: "de", wahl: "keine" });
    expect(gesamtAus(reihe({ herkunft: "keine", gesamt: null }), "")).toBeNull();
    expect(gesamtAus(reihe({ herkunft: "", gesamt: null, quelle_gesamt: null }), "")).toBeNull();
    expect(gesamtAus(reihe({ herkunft: "keine", gesamt: null }), "12")).toEqual({ sprache: "de", wahl: "eigene", zahl: 12 });
    expect(() => gesamtAus(reihe(), "0")).toThrow("Bände: ganze Zahl von 1 bis 9999");
    expect(() => gesamtAus(reihe(), "3,5")).toThrow();
  });

  it("fügt einen Platzhalter an der Schreibmarke ein und ersetzt eine Auswahl", () => {
    expect(einfuegen("https://katalog.example/?q=", "titel", 27)).toEqual({ text: "https://katalog.example/?q={titel}", marke: 34 });
    expect(einfuegen("a XX b", "autor", 2, 4)).toEqual({ text: "a {autor} b", marke: 9 });
  });

  it("gibt beim Hochladen in eine Lücke Sammlung, Band und Sprache vor", () => {
    expect(lueckenvorgabe(3, luecke())).toEqual({ sammlung_id: 3, band: "4", sprache: "de" });
  });
});

describe("Nur mit der Fähigkeit Lücken", () => {
  it("fragt ohne sie nicht nach den Lücken, mit ihr schon", async () => {
    darf("lesen", "bearbeiten");
    let f = server();
    const ohne = new Lueckenstand(3);
    await ohne.laden();
    expect(f).not.toHaveBeenCalled();
    expect(ohne.luecken).toBeNull();
    darf("lesen", "luecken");
    f = server();
    const mit = new Lueckenstand(3);
    await mit.laden();
    expect(f.mock.calls[0][0]).toBe("/api/collections/3/luecken");
    expect(mit.luecken?.reihen).toHaveLength(2);
  });

  it("lädt in eine Lücke über eine Vorschau mit Vorgabe hoch", async () => {
    const f = server({ id: "v-1", name: "", zeilen: [] });
    const nimm = vi.spyOn(annahme, "nimmAn").mockResolvedValue("v-1");
    await new Lueckenstand(3).hochladen([new File(["a"], "Kaiwind 4.epub")], luecke());
    expect(nimm).toHaveBeenCalledWith(expect.any(Array), false, { sammlung_id: 3, band: "4", sprache: "de" });
    await new Lueckenstand(3).hochladen([new File(["a"], "Stapel.zip")]);
    expect(nimm).toHaveBeenLastCalledWith(expect.any(Array), false, { sammlung_id: 3 });
    nimm.mockRestore();
    void f;
  });
});

describe("Regal und Feld zum fehlenden Band", () => {
  it("zeigt je Sprache eine Reihe mit Zahlen und den Platzhalter mit Nummer und Titel", async () => {
    darf("lesen", "luecken");
    server();
    const stand = new Lueckenstand(3);
    await stand.laden();
    render(Lueckenregal, { stand, art: "grid", reihe: ["Kaiwind"] });
    expect(screen.getByRole("heading", { name: "Deutsch" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Englisch" })).toBeTruthy();
    expect(screen.getByText("8 von 12")).toBeTruthy();
    expect(screen.getByText("es fehlen 4 und 9")).toBeTruthy();
    const platz = screen.getByRole("button", { name: "Band 4 fehlt: Der stille Kai" });
    expect(platz.getAttribute("aria-expanded")).toBe("false");
    await fireEvent.click(platz);
    expect(platz.getAttribute("aria-expanded")).toBe("true");
    expect(await screen.findByText("978-3-99999-004-0")).toBeTruthy();
  });

  it("bietet Suchen nur mit Suchadresse, Hochladen nur mit Hinzufügen und Ausblenden nur mit Bearbeiten", () => {
    const stand = new Lueckenstand(3);
    darf("lesen", "luecken", "hinzufuegen", "bearbeiten");
    const alles = render(Lueckenfeld, { luecke: luecke(), reihe: reihe(), stand, autor: "Jonte Marks", onschliessen: () => {} });
    expect(screen.getByRole("link", { name: "Suchen" }).getAttribute("href")).toBe("https://katalog.example/suche?q=Der%20stille%20Kai");
    expect(screen.getByRole("button", { name: "Hochladen" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Gibt es nicht" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Kopieren" }).className).not.toContain("voll");
    alles.unmount();
    darf("lesen", "luecken");
    render(Lueckenfeld, { luecke: luecke({ suchadresse: null, titel: "" }), reihe: reihe(), stand, autor: "Jonte Marks", onschliessen: () => {} });
    expect(screen.queryByRole("link", { name: "Suchen" })).toBeNull();
    expect(screen.getByRole("button", { name: "Kopieren" }).className).toContain("voll");
    expect(screen.queryByRole("button", { name: "Hochladen" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Gibt es nicht" })).toBeNull();
    expect(screen.getByText("unbekannt")).toBeTruthy();
  });
});

describe("Lücken einer Sammlung bearbeiten", () => {
  it("sammelt Platzhalter, eigene Zahl, ohne Zahl und den Weg zurück zur Quelle für das Speichern", async () => {
    darf("lesen", "luecken", "bearbeiten");
    server(luecken({ reihen: [reihe({ herkunft: "eigene", eigene: 15, gesamt: 15 }), reihe({ sprache: "en", name: "Englisch", gesamt: 5, quelle_gesamt: 5 })] }));
    const teil = render(Lueckenteil, { sammlung: 3 });
    const komponente = teil.component as unknown as { aenderung: () => unknown };
    const englisch = (await screen.findByLabelText("Bände auf Englisch")) as HTMLInputElement;
    expect(komponente.aenderung()).toBeNull();
    await fireEvent.input(englisch, { target: { value: "" } });
    await fireEvent.click(screen.getByRole("button", { name: "Zahl der Quellen nehmen (12)" }));
    await fireEvent.click(screen.getByRole("switch", { name: "Platzhalter im Regal" }));
    expect(komponente.aenderung()).toEqual({ an: false, gesamt: [{ sprache: "de", wahl: "quelle" }, { sprache: "en", wahl: "keine" }] });
  });

  it("holt einen ausgeblendeten Band zurück", async () => {
    darf("lesen", "luecken", "bearbeiten");
    const f = server(luecken({ ausgeblendet: [{ sprache: "de", name: "Deutsch", nummer: 9, grund: "gibt_es_nicht", grund_text: "Gibt es nicht", titel: "", am: "" }] }));
    render(Lueckenteil, { sammlung: 3 });
    await fireEvent.click(await screen.findByRole("button", { name: "Zurückholen" }));
    const [weg, o] = f.mock.calls.at(-1)!;
    expect(weg).toBe("/api/collections/3/luecken/zurueckholen");
    expect(JSON.parse(String(o?.body))).toEqual({ sprache: "de", nummer: 9 });
  });
});
