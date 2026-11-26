// Was ein Kind darf und wie es liest (BF-78): aus GET /api/familie/ich, Fehlendes aus den Vorgaben der Stufe; der Lesestand
// in der Form des normalen Lesers
import { darstellungAus, faehigkeitenAus, ichAus, katzeAus, lesezeitAus, nutztKinderbereich } from "../src/lib/kind/ich";
import { kindangabenAus, kinderlesewerte } from "../src/lib/kind/stelle";
import { lesestand } from "../src/lib/lesestand";
import { einheitenAus, textstueckeAus } from "../src/lib/kind/quelle-text";

describe("Fähigkeiten", () => {
  it("liest Listen und Schalter und lässt Unbekanntes weg", () => {
    expect([...faehigkeitenAus(["lesen", "vorlesen", "ki"], "schule")]).toEqual(["lesen", "vorlesen"]);
    expect([...faehigkeitenAus({ lesen: true, suche: true, notizen: false }, "schule")]).toEqual(["lesen", "suche"]);
  });

  it("nimmt ohne Angabe die Vorgaben der Stufe: für kleine Kinder nur Lesen und Vorlesen, Suche und Notizen erst ab Schule", () => {
    expect([...faehigkeitenAus(undefined, "vorlesen")]).toEqual(["lesen", "vorlesen"]);
    expect([...faehigkeitenAus(undefined, "erstes_lesen")]).toEqual(["lesen", "vorlesen"]);
    const lernen = faehigkeitenAus(undefined, "lesen_lernen");
    expect(["favoriten", "gelesen"].every((f) => lernen.has(f as never))).toBe(true);
    expect(["suche", "notizen", "markierungen", "lesezeichen"].some((f) => lernen.has(f as never))).toBe(false);
    const schule = faehigkeitenAus(undefined, "schule");
    expect(["suche", "markierungen", "notizen", "lesezeichen"].every((f) => schule.has(f as never))).toBe(true);
  });

  it("ergänzt die Darstellung aus der Stufe und hält Grenzen ein", () => {
    const d = darstellungAus({ groesse: 40, tippflaeche_mm: 5, tempo: 9 }, "vorlesen");
    expect(d.groesse).toBe(40);
    expect(d.tippflaeche_mm).toBe(11.6);
    expect(d.tempo).toBe(1.5);
    expect(d.woerter_je_zeile).toBe(4);
    expect(d.vorlesen_von_selbst).toBe(true);
    expect(d.schrift).toContain("Andika");
    expect(darstellungAus({}, "vorlesen").tippflaeche_mm).toBe(20.1);
  });

  it("liest GET /api/familie/ich, wie der Server es schickt", () => {
    const ich = ichAus({
      profil: { id: "k2", rolle: "kind", stufe: "lesen_lernen", einstellungen: { lesehilfen: { silben: true }, lesezeit: { an: true, minuten: 45, ruhe_an: true, ruhe_von: "19:30", ruhe_bis: "06:30" } } },
      faehigkeiten: ["lesen", "vorlesen", "favoriten"],
      darstellung: { schrift: "kinderschrift", groesse_px: 29, fett: false, woerter_je_zeile: null, zeichen_je_zeile: 60, zeilenabstand: 1.5, absatz: 2, buchstabe: 0.12, wort: 0.16, tippflaeche_px: 76, symbole: true },
      lesehilfen: { mitlesen: true, tempo: 0.8, silben: false, lesezeile: true, schrift: "gross", hinweise_sprechen: true, tasten_ansagen: false, stimme: "" },
      lesezeit: { an: true, heute_s: 120, grenze_s: 2700, rest_s: 2580, hinweis_ab_s: 2400, ruht: false, ruhe_bis: null },
      katze: { an: true, name: "Luna", schnurren: false, name_eingabe: "tippen" },
      einblick: ["titel", "lesezeit", "fortschritt"],
    });
    // Die Schriftwahl der Eltern hat der Server schon eingerechnet
    expect(ich.darstellung.groesse).toBe(29);
    expect(ich.darstellung.woerter_je_zeile).toBe(0);
    expect(ich.darstellung.zeichen_je_zeile).toBe(60);
    expect(ich.darstellung.abstand_absatz).toBe(2);
    expect(ich.darstellung.tippflaeche_mm).toBe(20.1);
    // ich.lesehilfen geht den gespeicherten Einstellungen vor
    expect(ich.darstellung.silben).toBe(false);
    expect(ich.darstellung.tempo).toBe(0.8);
    expect(ich.darstellung.tasten_ansagen).toBe(false);
    expect(ich.darstellung.schrift).toContain("Andika");
    expect(ich.lesezeit.ruhe_ab).toBe("19:30");
    expect(ich.lesezeit.grenze_s).toBe(2700);
    expect(ich.einblick).toEqual(["titel", "lesezeit", "fortschritt"]);
    expect(darstellungAus({ schrift: "serifenlos", zeichen_je_zeile: null }, "schule").schrift).toContain("Atkinson");
    expect(darstellungAus({ zeichen_je_zeile: null }, "schule").zeichen_je_zeile).toBe(0);
    // Den Rückblick gibt es nur mit der Fähigkeit gelesen vom Server, nie von selbst
    expect(ich.faehigkeiten.has("gelesen")).toBe(false);
    expect(faehigkeitenAus(["lesen", "favoriten", "gelesen"], "lesen_lernen").has("gelesen")).toBe(true);
  });

  it("baut ein vollständiges Ich, auch aus wenig", () => {
    const ich = ichAus({ profil: { id: "k1", name: "Kim", rolle: "kind", stufe: "erstes_lesen" }, katze: { name: " Flocke " } });
    expect(ich.profil.stufe).toBe("erstes_lesen");
    expect(ich.profil.zeichen).toBe("face-smile");
    expect(ich.katze).toEqual({ an: true, name: "Flocke", schnurren: false, name_eingabe: "tippen" });
    expect(ich.lesezeit).toEqual({ heute_s: 0, grenze_s: null, rest_s: null, ruht: false, ruhe_bis: null, ruhe_ab: null, hinweis_ab_s: null });
    expect(ich.darstellung.lesezeile).toBe(true);
    expect(nutztKinderbereich(ich)).toBe(true);
    expect(nutztKinderbereich(ichAus({ profil: { rolle: "kind", stufe: "jugend" } }))).toBe(false);
    expect(nutztKinderbereich(ichAus({ profil: { rolle: "erwachsen" } }))).toBe(false);
  });

  it("liest Lesezeit und Katze tolerant", () => {
    expect(lesezeitAus({ an: true, heute_s: 90, grenze_s: 100, rest_s: 10, ruht: true, ruhe_bis: "07:00", hinweis_ab_s: 0 }, { ruhe_an: true, ruhe_von: "19:30" })).toEqual({ heute_s: 90, grenze_s: 100, rest_s: 10, ruht: true, ruhe_bis: "07:00", ruhe_ab: "19:30", hinweis_ab_s: 0 });
    expect(lesezeitAus({}, { ruhe_an: false, ruhe_von: "19:30" }).ruhe_ab).toBeNull();
    expect(katzeAus({ an: false, schnurren: true })).toEqual({ an: false, name: "", schnurren: true, name_eingabe: "vorschlaege" });
    expect(katzeAus({ name_eingabe: "tippen" }).name_eingabe).toBe("tippen");
  });
});

describe("Lesestand des Kinderlesers", () => {
  it("schreibt die Form des normalen Lesers und dazu Stelle und Lesezeichen", () => {
    const w = kinderlesewerte({ page: 3 }, { einheit: 2, zeichen: 40 }, { einheit: 1, zeichen: 0 });
    const position = `pdf:${JSON.stringify(w)}`;
    expect(kindangabenAus(position)).toEqual({ einheit: 2, zeichen: 40, lesezeichen: { einheit: 1, zeichen: 0 } });
    // Am Ende steht der Lesestand auf dem Ende: so gilt das Buch nach der Regel des Servers als fertig
    const ende = `epub:${JSON.stringify(kinderlesewerte({ cfi: "epubcfi(/6/8!/4/2/1:0)", percent: 100 }, { einheit: 3, zeichen: 0 }, null))}`;
    expect(lesestand({ reading_position: ende, page_count: 0 }).anteil).toBe(1);
  });

  it("versteht Stände des normalen Lesers", () => {
    expect(kindangabenAus('epub:{"cfi":"epubcfi(/6/4!/4/2/1:0)","percent":40}')).toBeNull();
    expect(kindangabenAus("")).toBeNull();
  });
});
