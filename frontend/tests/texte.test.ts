import { zerlege, ersteMarkierung } from "../src/lib/auszug";
import { anzahl, datum, groesse, zahl, zeitpunkt } from "../src/lib/format";
import { filtername, nurText, ohneFilter } from "../src/ansichten/suche/suchsprache";
import { dreiklang } from "../src/lib/farben";
import { matchRoute } from "../src/lib/router.svelte";
import { neuerAls } from "../src/lib/stand/verbindungen.svelte";

describe("Auszüge", () => {
  it("lässt nur mark und b als Auszeichnung zu", () => {
    expect(zerlege("vor <mark>Wort</mark> <img src=x onerror=1> nach")).toEqual([
      { text: "vor ", markiert: false },
      { text: "Wort", markiert: true },
      { text: " <img src=x onerror=1> nach", markiert: false },
    ]);
  });

  it("macht maskierte Zeichen wieder zu Text, auch ein maskiertes mark", () => {
    expect(zerlege("a &lt;b&gt; &amp; &lt;mark&gt;")).toEqual([{ text: "a <b> & <mark>", markiert: false }]);
  });

  it("findet die erste Markierung", () => {
    expect(ersteMarkierung("x <b>Netz</b> y <mark>z</mark>")).toBe("Netz");
    expect(ersteMarkierung("")).toBe("");
  });
});

describe("Zahlen und Zeiten", () => {
  it("schreibt deutsch", () => {
    expect(zahl(4734)).toBe("4.734");
    expect(groesse(0)).toBe("0 Byte");
    expect(groesse(48_200_000)).toBe("48,2 MB");
    expect(groesse(262_000_000)).toBe("262 MB");
    expect(anzahl(1, "Buch", "Bücher")).toBe("1 Buch");
    expect(anzahl(0, "Buch", "Bücher")).toBe("0 Bücher");
  });

  it("liest Zeiten ohne Zone als Weltzeit", () => {
    expect(zeitpunkt("2026-11-25 19:54:47")?.toISOString()).toBe("2026-11-25T19:54:47.000Z");
    expect(zeitpunkt("2026-11-25T21:00:00Z")?.toISOString()).toBe("2026-11-25T21:00:00.000Z");
    expect(datum("kein Datum")).toBe("");
  });
});

describe("Suchsprache", () => {
  it("nimmt einzelne Filter heraus", () => {
    expect(ohneFilter('Schichten autor:"Anne Lindner" format:pdf', "autor")).toBe("Schichten format:pdf");
    expect(ohneFilter("Schichten datum:>=2020", "ab")).toBe("Schichten");
    expect(filtername("zeitraum")).toBe("datum");
  });

  it("lässt für die Bedeutung nur den freien Text", () => {
    expect(nurText('"in Schichten" author:Lindner format:epub date:2023')).toBe("in Schichten");
    expect(nurText("autor:HalloWelt42")).toBe("");
  });
});

describe("Farben eines Umschlags", () => {
  it("findet drei verschiedene Töne", () => {
    const punkte: number[] = [];
    for (let n = 0; n < 60; n++) punkte.push(200, 20, 20, 255);
    for (let n = 0; n < 40; n++) punkte.push(20, 40, 190, 255);
    for (let n = 0; n < 20; n++) punkte.push(240, 230, 200, 255);
    const drei = dreiklang(new Uint8ClampedArray(punkte))!;
    expect(new Set(drei).size).toBe(3);
    expect(drei[0]).toBe("#c81414");
  });

  it("kennt kein Bild ohne Punkte", () => {
    expect(dreiklang(new Uint8ClampedArray([0, 0, 0, 0]))).toBeNull();
  });
});

describe("Adressen", () => {
  it("erkennt alle alten Wege", () => {
    expect(matchRoute("/book/:id/read", "/book/12/read")).toEqual({ id: "12" });
    expect(matchRoute("/book/:id", "/book/12/read")).toBeNull();
    expect(matchRoute("/settings/*", "/settings/ai")).toEqual({});
    expect(matchRoute("/collection/:id", "/collection/3")).toEqual({ id: "3" });
  });

  it("hält nur höhere Fassungen für neu", () => {
    expect(neuerAls("0.14.1", "0.14.0")).toBe(true);
    expect(neuerAls("0.13.9", "0.14.0")).toBe(false);
    expect(neuerAls("0.14.0", "0.14.0")).toBe(false);
  });
});
