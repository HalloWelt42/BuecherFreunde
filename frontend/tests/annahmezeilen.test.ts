import { fuegeZusammen, laeuftVonSelbst } from "../src/lib/annahme/zeilen";
import type { AnnahmeEintrag, Hochladung } from "../src/lib/annahme/typen";

function eintrag(ueber: Partial<AnnahmeEintrag>): AnnahmeEintrag {
  return { id: 1, name: "Buch.pdf", groesse: 1000, sha256: "", empfangen: 0, teil_groesse: 4, stand: "wartet", schritt: 1, anteil: 0, text: "Text", buch_id: null, quelle: "hochladen", angelegt_am: "", geaendert_am: "", ...ueber };
}

function hochladung(ueber: Partial<Hochladung>): Hochladung {
  return { schluessel: "datei-1", name: "Buch.pdf", groesse: 1000, lage: "laedt", anteil: 0.4, gesendet: 400, text: "Wird abgelegt", eintrag: null, ...ueber };
}

const eine = (e: Partial<AnnahmeEintrag>) => fuegeZusammen([eintrag(e)], [])[0];

describe("Zeilen der Annahme", () => {
  it("ordnet jeden Stand einer Gruppe zu", () => {
    expect(eine({ stand: "liest", empfangen: 1000 }).gruppe).toBe("laeuft");
    expect(eine({ stand: "wissen" }).gruppe).toBe("fertig");
    expect(eine({ stand: "fertig" }).gruppe).toBe("fertig");
    expect(eine({ stand: "da" }).gruppe).toBe("da");
    for (const stand of ["format", "kaputt", "fehler", "ohne_text"] as const) expect(eine({ stand }).gruppe).toBe("klaeren");
  });

  it("zeigt sechs Stationen, die laufende mit Füllstand", () => {
    const z = eine({ stand: "liest", schritt: 2, anteil: 0.7, empfangen: 1000 });
    expect(z.stationen).toEqual(["fertig", "fertig", "jetzt", "offen", "offen", "offen"]);
    expect(z.prozent).toBe(70);
  });

  it("zeigt fertige Aufnahmen ganz grün und wartende Bedeutung gestrichelt", () => {
    expect(eine({ stand: "fertig", schritt: 6 }).stationen).toEqual(Array(6).fill("fertig"));
    expect(eine({ stand: "wissen", schritt: 5 }).stationen[5]).toBe("wartet");
  });

  it("öffnet das Buch nur, wenn es eines gibt", () => {
    expect(eine({ stand: "da", buch_id: 4 }).handlungen).toEqual(["buch"]);
    expect(eine({ stand: "da" }).handlungen).toEqual([]);
  });

  it("bittet nach dem Neuladen um die Datei", () => {
    const z = eine({ stand: "laedt", empfangen: 410 });
    expect(z.handlungen).toEqual(["waehlen", "entfernen"]);
    expect(z.prozent).toBe(41);
  });

  it("zählt nur, was von selbst vorankommt", () => {
    expect(laeuftVonSelbst(eine({ stand: "liest", empfangen: 1000 }))).toBe(true);
    expect(laeuftVonSelbst(eine({ stand: "laedt", empfangen: 410 }))).toBe(false);
    expect(laeuftVonSelbst(fuegeZusammen([], [hochladung({ lage: "ohne_verbindung" })])[0])).toBe(true);
    expect(laeuftVonSelbst(fuegeZusammen([], [hochladung({ lage: "angehalten" })])[0])).toBe(false);
  });

  it("stellt laufende Hochladungen nach oben und verdeckt ihren Eintrag", () => {
    const zeilen = fuegeZusammen([eintrag({ id: 2 }), eintrag({ id: 1, stand: "fertig" })], [hochladung({ eintrag: eintrag({ id: 2 }) })]);
    expect(zeilen.map((z) => z.schluessel)).toEqual(["datei-1", "eintrag-1"]);
    expect(zeilen[0].handlungen).toEqual(["anhalten"]);
  });

  it("überlässt dem Server die Zeile, sobald alles geschickt ist", () => {
    const zeilen = fuegeZusammen([eintrag({ id: 2, stand: "liest", empfangen: 1000 })], [hochladung({ lage: "beim_server", eintrag: eintrag({ id: 2 }) })]);
    expect(zeilen.map((z) => z.schluessel)).toEqual(["eintrag-2"]);
  });

  it("nennt den Abriss und bietet an, gleich weiterzumachen", () => {
    const [z] = fuegeZusammen([], [hochladung({ lage: "ohne_verbindung" })]);
    expect(z.wort).toBe("Wartet auf Verbindung");
    expect(z.handlungen[0]).toBe("jetzt");
  });
});
