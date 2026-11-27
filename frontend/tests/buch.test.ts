import { leseKnopf, lesestand, lesewerte, leseweise, standText, stellenAdresse } from "../src/lib/lesestand";
import { fundart, gleichwertig, nutzlast, vergleiche } from "../src/ansichten/buch/angaben";

const buch = (reading_position: string, page_count = 200) => ({ reading_position, page_count });

describe("Lesestand", () => {
  it("liest alle gespeicherten Formen", () => {
    expect(lesewerte('pdf:{"page":41,"papier":"sepia"}')).toEqual({ page: 41, papier: "sepia" });
    expect(lesewerte("page:7").page).toBe(7);
    expect(lesewerte("cfi:epubcfi(/6/4)").cfi).toBe("epubcfi(/6/4)");
    expect(lesewerte("txt:30").scrollPct).toBe(30);
    expect(lesewerte("percent:12").percent).toBe(12);
    expect(lesewerte("pdf:{kaputt")).toEqual({});
  });

  it("rechnet den Anteil je Form, auch für Textbücher", () => {
    expect(lesestand(buch('pdf:{"page":50}')).anteil).toBe(0.25);
    expect(lesestand(buch('epub:{"percent":62}')).anteil).toBeCloseTo(0.62);
    expect(lesestand(buch('txt:{"scrollPct":10}')).anteil).toBeCloseTo(0.1);
    expect(lesestand(buch("")).angefangen).toBe(false);
  });

  it("beschriftet Knopf und Zeile", () => {
    expect(leseKnopf(buch(""))).toBe("Lesen");
    expect(leseKnopf(buch('pdf:{"page":210}', 1104))).toBe("Weiterlesen, Seite 210");
    expect(standText(buch('pdf:{"page":210}', 1104))).toBe("Seite 210 von 1.104");
    expect(leseweise('pdf:{"page":1,"papier":"sepia","ansicht":"breite"}')).toEqual(["Papier sepia", "Seitenbreite"]);
  });

  it("springt je Format an die richtige Stelle", () => {
    expect(stellenAdresse(4, "pdf", { cfi: "page:5" })).toBe("/book/4/read?page=5");
    expect(stellenAdresse(4, "pdf", { seite: 12 })).toBe("/book/4/read?page=12");
    expect(stellenAdresse(4, "epub", { cfi: "epubcfi(/6/4)" })).toBe("/book/4/read?cfi=epubcfi%28%2F6%2F4%29");
    expect(stellenAdresse(4, "md", { cfi: "percent:33.5" })).toBe("/book/4/read?percent=33.5");
  });
});

describe("Angaben vergleichen", () => {
  const vorschlag = { titel: "Verteiler", verlag: "Beispielverlag", jahr: 2026, kategorien: ["Netzwerke", "Fachbuch"], cover_url: "/bild.jpg", raw: { subjects: ["Router", "Netzwerke"], n: 3 } };
  const aktuell = { titel: "Verteiler", verlag: "", jahr: null, kategorien: ["Netzwerke"], hat_cover: true };

  it("wählt nur Unterschiede vor", () => {
    const zeilen = vergleiche(vorschlag, aktuell, "/alt.jpg");
    const wahl = Object.fromEntries(zeilen.map((z) => [z.schluessel, z.gewaehlt]));
    expect(wahl).toEqual({ titel: false, verlag: true, jahr: true, cover: true, kategorien: true });
    expect(zeilen.find((z) => z.schluessel === "kategorien")?.neu).toBe("dazu: Fachbuch");
  });

  it("nimmt andere Schreibweisen derselben Angabe nicht als Unterschied", () => {
    expect(gleichwertig("isbn", "978-3-99999-127-6", "9783999991276")).toBe(true);
    expect(gleichwertig("autor", "Erika Beispiel", "Beispiel Erika")).toBe(true);
    expect(gleichwertig("autor", "Beispiel, Erika", "Erika Beispiel")).toBe(false);
    const zeilen = vergleiche({ titel: "Tragwerk", isbn: "9783999991276" }, { titel: "TRAGWERK", isbn: "978-3-99999-127-6" }, "");
    expect(zeilen.map((z) => [z.schluessel, z.gleich, z.gewaehlt])).toEqual([["titel", false, false], ["isbn", true, false]]);
  });

  it("nennt die Quelle je Feld und wie gefunden wurde", () => {
    const v = { titel: "Hexagonal - Saubere Architektur", jahr: 2026, cover_url: "/b.jpg", herkunft: { titel: "dnb", cover_url: "open_library" } };
    const zeilen = vergleiche(v, { titel: "Hexagonal", jahr: null }, "", { dnb: "Verzeichnis 3", open_library: "Verzeichnis 2" });
    expect(zeilen.map((z) => z.herkunft)).toEqual(["Verzeichnis 3", undefined, "Verzeichnis 2"]);
    expect(fundart({ fund: "isbn" })?.ton).toBe("gut");
    expect(fundart({ fund: "titel", sicher: false })?.ton).toBe("warn");
    expect(fundart({})).toBeNull();
  });

  it("legt schon vorhandene Regale ohne Rücksicht auf Groß und klein nicht noch einmal an", () => {
    const z = vergleiche({ kategorien: ["romane", "Klassiker"] }, { kategorien: ["Romane"] }, "").find((x) => x.schluessel === "kategorien");
    expect(z?.neu).toBe("dazu: Klassiker");
  });

  it("sendet nur Gewähltes, Listen als Regale", () => {
    expect(nutzlast(vorschlag, "open_library", new Set(["verlag"]), new Set())).toEqual({ verlag: "Beispielverlag" });
    expect(nutzlast(vorschlag, "open_library", new Set(["cover"]), new Set(["subjects", "n"]))).toEqual({ cover_url: "/bild.jpg", quelle: "open_library", kategorien: ["Router", "Netzwerke"] });
  });
});
