import { ansichtOder, einpassen, geblaettert, naechsteStufe, sichtbareSeiten } from "../src/lib/leser/pdf/zoom";
import { Pdfmarkierungen } from "../src/lib/leser/pdf/markierung";
import type { Markierung } from "../src/lib/typen";

describe("Zoom", () => {
  it("geht jede Stufe einzeln, auch von Zwischenwerten aus", () => {
    expect(naechsteStufe(1, 1)).toBe(1.25);
    expect(naechsteStufe(1, -1)).toBe(0.75);
    expect(naechsteStufe(1.1, 1)).toBe(1.25);
    expect(naechsteStufe(1.1, -1)).toBe(1);
  });

  it("bleibt über der größten Stufe bei ihr und springt nie auf die kleinste", () => {
    expect(naechsteStufe(3.4, -1)).toBe(3);
    expect(naechsteStufe(3.4, 1)).toBe(3);
    expect(naechsteStufe(0.4, -1)).toBe(0.5);
  });

  it("passt Breite, Seite und Doppelseite ein", () => {
    const seite = { breite: 500, hoehe: 700 };
    expect(einpassen("breite", seite, { breite: 1000, hoehe: 700 })).toBe(2);
    expect(einpassen("seite", seite, { breite: 1000, hoehe: 700 })).toBe(1);
    expect(einpassen("doppel", seite, { breite: 1016, hoehe: 7000 })).toBe(1);
    expect(einpassen("scroll", seite, { breite: 1000, hoehe: 700 })).toBeNull();
    expect(einpassen("breite", seite, { breite: 0, hoehe: 0 })).toBeNull();
  });

  it("zeigt in der Doppelseite die ungerade links", () => {
    expect(sichtbareSeiten("doppel", 6, 10)).toEqual([5, 6]);
    expect(sichtbareSeiten("doppel", 5, 5)).toEqual([5]);
    expect(sichtbareSeiten("einzeln", 4, 10)).toEqual([4]);
    expect(geblaettert("breite")).toBe(false);
  });

  it("nimmt nur bekannte Ansichten an", () => {
    expect(ansichtOder("doppel", "scroll")).toBe("doppel");
    expect(ansichtOder("text", "scroll")).toBe("scroll");
    expect(ansichtOder("quer", "breite")).toBe("breite");
  });
});

describe("Markierungen auf der Textebene", () => {
  // Hervorhebungs-Schnittstelle des Browsers, wie Chrome und Safari sie haben (jsdom kennt sie nicht)
  class Hervorhebung extends Set<Range> {
    priority = 0;
    constructor(...bereiche: Range[]) {
      super(bereiche);
    }
  }
  const register = new Map<string, Hervorhebung>();
  beforeAll(() => {
    Object.assign(window, { Highlight: Hervorhebung });
    Object.assign(window.CSS ?? Object.assign(window, { CSS: {} }).CSS, { highlights: register });
  });
  afterAll(() => {
    delete (window as { Highlight?: unknown }).Highlight;
    delete (window.CSS as { highlights?: unknown }).highlights;
  });
  beforeEach(() => register.clear());

  // Die Textebene von pdf.js: ein Stück je Lauf, oft eine ganze Zeile
  const ebene = () => {
    const rahmen = document.createElement("div");
    const d = document.createElement("div");
    d.className = "textLayer";
    for (const t of ["Für einen gewöhnlichen Büro-PC sind 256 MByte RAM ein vernünftiger Wert.", "Zwei Rechner an einem Kabel", "verstehen sich ", "", "noch nicht."]) {
      const s = document.createElement("span");
      s.textContent = t;
      d.append(s);
    }
    rahmen.append(d);
    document.body.append(rahmen);
    return d;
  };
  const marke = (text: string, seite = 3, id = 7, color = "#FFEE58"): Markierung => ({ id, book_id: 1, cfi_range: `page:${seite}`, color, text_snippet: text, label_name: "", label_note: "", created_at: "" });
  const gemalt = () => [...register].flatMap(([name, h]) => [...h].map((r) => `${name}: ${r.toString()}`));

  it("malt genau die gewählten Zeichen, nicht das ganze Stück der Zeile", () => {
    const m = new Pdfmarkierungen();
    m.beschrifte(3, ebene(), [marke("gewöhnlichen Büro-PC")]);
    expect(gemalt()).toEqual(["bf-stift-FFEE58: gewöhnlichen Büro-PC"]);
    m.leere();
  });

  it("findet Wortlaut über Stücke hinweg und nur auf der eigenen Seite", () => {
    const m = new Pdfmarkierungen();
    m.beschrifte(3, ebene(), [marke("verstehen sich noch")]);
    expect(gemalt()).toEqual(["bf-stift-FFEE58: verstehen sich noch"]);
    m.beschrifte(4, ebene(), [marke("Kabel", 3)]);
    expect(gemalt()).toEqual(["bf-stift-FFEE58: verstehen sich noch"]);
    m.leere();
  });

  it("malt je Farbe alle gezeichneten Seiten zusammen und vergisst weggeräumte", () => {
    const m = new Pdfmarkierungen();
    const drei = ebene();
    m.beschrifte(3, drei, [marke("Kabel"), marke("Zwei", 4, 8)]);
    m.beschrifte(4, ebene(), [marke("Kabel"), marke("Zwei", 4, 8)]);
    expect(gemalt().sort()).toEqual(["bf-stift-FFEE58: Kabel", "bf-stift-FFEE58: Zwei"]);
    expect(m.bereich(7)?.toString()).toBe("Kabel");
    drei.parentElement!.remove();
    m.beschrifte(4, ebene(), [marke("Zwei", 4, 8)]);
    expect(gemalt()).toEqual(["bf-stift-FFEE58: Zwei"]);
    expect(m.bereich(7)).toBeNull();
    m.leere();
    expect(gemalt()).toEqual([]);
  });

  it("findet die Fundstelle zeichengenau trotz anderem Leerraum", () => {
    const m = new Pdfmarkierungen();
    const fund = m.beschrifte(3, ebene(), [], "einem  Kabel\nverstehen");
    expect(fund?.toString()).toBe("einem Kabelverstehen");
    expect(gemalt()).toEqual(["bf-treffer: einem Kabelverstehen"]);
    expect(new Pdfmarkierungen().beschrifte(3, ebene(), [], "gibt es nicht")).toBeNull();
    m.leere();
  });

  it("lässt beim Aufräumen stehen, was eine andere Ansicht inzwischen malt", () => {
    const m = new Pdfmarkierungen();
    m.beschrifte(3, ebene(), [marke("Kabel")]);
    const fremd = new Hervorhebung();
    register.set("bf-stift-FFEE58", fremd);
    m.leere();
    expect(register.get("bf-stift-FFEE58")).toBe(fremd);
  });
});
