import { gemerkt, leseziel, nenntStelle } from "../src/lib/leser/ziel";

describe("Leseziel aus der Adresse", () => {
  it("liest alle Parameter", () => {
    const z = leseziel("?page=41&zoom=125&ansicht=breite&papier=sepia&q=Schichten&stelle=Jede%20Schicht&restart=1");
    expect(z).toMatchObject({ seite: 41, zoom: 125, ansicht: "breite", papier: "sepia", wort: "Schichten", stelle: "Jede Schicht", vonVorn: true });
  });

  it("versteht cfi=page:N als Seite eines PDF", () => {
    expect(leseziel("?cfi=page:9")).toMatchObject({ seite: 9, cfi: "" });
  });

  it("versteht cfi=percent:N und das alte pos als Anteil eines Textes", () => {
    expect(leseziel("?cfi=percent:51.7")).toMatchObject({ prozent: 51.7, cfi: "" });
    expect(leseziel("?pos=30")).toMatchObject({ prozent: 30 });
  });

  it("lässt eine Stelle im EPUB stehen", () => {
    expect(leseziel("?cfi=epubcfi(/6/4!/4/2)").cfi).toBe("epubcfi(/6/4!/4/2)");
  });

  it("weiß, ob die Adresse selbst eine Stelle nennt", () => {
    expect(nenntStelle(leseziel(""))).toBe(false);
    expect(nenntStelle(leseziel("?papier=dunkel"))).toBe(false);
    expect(nenntStelle(leseziel("?q=Deich"))).toBe(true);
  });

  it("verwirft von vorn nur die Stelle, nicht Schrift und Farben", () => {
    const w = { page: 12, cfi: "x", percent: 40, scrollPct: 3, fontSize: 130, fgColor: "#111111", papier: "sepia" };
    expect(gemerkt(leseziel("?restart=1"), w)).toEqual({ fontSize: 130, fgColor: "#111111", papier: "sepia" });
    expect(gemerkt(leseziel(""), w)).toEqual(w);
  });
});
