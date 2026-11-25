import { ansichtOder, einpassen, geblaettert, naechsteStufe, sichtbareSeiten } from "../src/lib/leser/pdf/zoom";
import { leereEbene, zeichneFundstelle, zeichneMarkierungen } from "../src/lib/leser/pdf/markierung";
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
  const ebene = () => {
    const d = document.createElement("div");
    for (const t of ["Zwei Rechner an einem Kabel", "verstehen sich ", "", "noch nicht."]) {
      const s = document.createElement("span");
      s.textContent = t;
      d.append(s);
    }
    return d;
  };
  const marke = (text: string, seite = 3): Markierung => ({ id: 7, book_id: 1, cfi_range: `page:${seite}`, color: "#FFEE58", text_snippet: text, label_name: "", label_note: "", created_at: "" });

  it("färbt nur die getroffenen Stücke der richtigen Seite", () => {
    const e = ebene();
    zeichneMarkierungen(e, 3, [marke("verstehen sich noch")]);
    expect([...e.children].map((s) => (s as HTMLElement).dataset.markierung ?? "")).toEqual(["", "7", "", "7"]);
    const f = ebene();
    zeichneMarkierungen(f, 4, [marke("verstehen sich noch")]);
    expect(f.querySelector("[data-markierung]")).toBeNull();
  });

  it("findet die Fundstelle trotz anderem Leerraum und räumt wieder auf", () => {
    const e = ebene();
    expect(zeichneFundstelle(e, "einem  Kabel\nverstehen")?.textContent).toBe("Zwei Rechner an einem Kabel");
    leereEbene(e);
    expect(e.querySelector("[data-markierung]")).toBeNull();
    expect(zeichneFundstelle(e, "gibt es nicht")).toBeNull();
  });
});
