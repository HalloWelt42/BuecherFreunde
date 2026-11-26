// Aufteilung des Leseraums (BF-35, BF-36, BF-41): Rand für die Marken, Feld daneben, Breite des Blatts
import { blattbreite, hoechsteSeitenbreite, MARKENRAND, teileAuf, type Raumlage } from "../src/lib/leser/leseraum.svelte";
import { einpassen } from "../src/lib/leser/pdf/zoom";

const lage = (teil: Partial<Raumlage>): Raumlage => ({ breite: 1428, feld: 320, rand: 16, telefon: false, vollbild: false, marken: true, feldOffen: false, ...teil });

describe("Aufteilung des Leseraums", () => {
  it("hält rechts einen Rand für die breiten Marken frei, nur wenn sie an sind", () => {
    expect(teileAuf(lage({}))).toEqual({ markenrand: MARKENRAND, feldDaneben: false, rechts: MARKENRAND });
    expect(teileAuf(lage({ marken: false }))).toEqual({ markenrand: 0, feldDaneben: false, rechts: 0 });
  });

  it("gibt dem offenen Feld seinen Platz neben dem Blatt, wenn das Blatt breit genug bleibt", () => {
    const a = teileAuf(lage({ feldOffen: true }));
    expect(a.feldDaneben).toBe(true);
    expect(a.rechts).toBe(MARKENRAND + 320 + 10);
    // Tablet hochkant: zu schmal, das Feld schwebt darüber wie bisher
    expect(teileAuf(lage({ breite: 822, feldOffen: true })).feldDaneben).toBe(false);
  });

  it("ändert am Telefon und im Vollbild nichts", () => {
    expect(teileAuf(lage({ telefon: true, feldOffen: true }))).toEqual({ markenrand: 0, feldDaneben: false, rechts: 0 });
    expect(teileAuf(lage({ vollbild: true, feldOffen: true }))).toEqual({ markenrand: 0, feldDaneben: false, rechts: 0 });
  });
});

describe("Breite des Blatts", () => {
  it("bleibt in ihren Grenzen und Schritten", () => {
    const { min, max } = blattbreite.bereich;
    blattbreite.wert = 10;
    expect(blattbreite.wert).toBe(min);
    blattbreite.wert = 99999;
    expect(blattbreite.wert).toBe(max);
    blattbreite.wert = 731;
    expect(blattbreite.wert).toBe(740);
    blattbreite.wert = blattbreite.bereich.vorgabe;
  });

  it("gilt für die Seite im PDF am Rechner, nicht im Vollbild und nicht am Telefon", () => {
    expect(hoechsteSeitenbreite({ telefon: false, vollbild: false })).toBe(blattbreite.wert);
    expect(hoechsteSeitenbreite({ telefon: false, vollbild: true })).toBe(Infinity);
    expect(hoechsteSeitenbreite({ telefon: true, vollbild: false })).toBe(Infinity);
  });

  it("begrenzt im PDF die Seite beim Einpassen, in der Doppelseite jede der beiden", () => {
    const seite = { breite: 500, hoehe: 700 };
    expect(einpassen("breite", seite, { breite: 1400, hoehe: 700 }, 800)).toBe(1.6);
    expect(einpassen("breite", seite, { breite: 600, hoehe: 700 }, 800)).toBe(1.2);
    expect(einpassen("seite", seite, { breite: 1400, hoehe: 2000 }, 600)).toBe(1.2);
    expect(einpassen("doppel", seite, { breite: 2016, hoehe: 7000 }, 600)).toBe(1.2);
    expect(einpassen("doppel", seite, { breite: 1016, hoehe: 7000 }, 800)).toBe(1);
  });
});
