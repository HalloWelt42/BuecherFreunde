// Was ein Kind darf und wie es liest (BF-78): aus GET /api/familie/ich, Fehlendes aus den Vorgaben der Stufe; der Lesestand
// in der Form des normalen Lesers
import { darstellungAus, faehigkeitenAus, ichAus, katzeAus, lesezeitAus, nutztKinderbereich } from "../src/lib/kind/ich";
import { fertigGelesen, kindangabenAus, kinderlesewerte } from "../src/lib/kind/stelle";
import { einheitenAus, textstueckeAus } from "../src/lib/kind/quelle-text";

describe("Fähigkeiten", () => {
  it("liest Listen und Schalter und lässt Unbekanntes weg", () => {
    expect([...faehigkeitenAus(["lesen", "vorlesen", "ki"], "schule")]).toEqual(["lesen", "vorlesen"]);
    expect([...faehigkeitenAus({ lesen: true, suche: true, notizen: false }, "schule")]).toEqual(["lesen", "suche"]);
  });

  it("nimmt ohne Angabe die Vorgaben der Stufe: anfangs nur Lesen, Vorlesen, ein Lesezeichen", () => {
    expect([...faehigkeitenAus(undefined, "vorlesen")]).toEqual(["lesen", "vorlesen", "lesezeichen"]);
    expect([...faehigkeitenAus(undefined, "erstes_lesen")]).toEqual(["lesen", "vorlesen", "lesezeichen"]);
    const lernen = faehigkeitenAus(undefined, "lesen_lernen");
    expect(["suche", "favoriten", "gelesen"].every((f) => lernen.has(f as never))).toBe(true);
    expect(lernen.has("notizen")).toBe(false);
    const schule = faehigkeitenAus(undefined, "schule");
    expect(schule.has("markierungen") && schule.has("notizen")).toBe(true);
  });

  it("ergänzt die Darstellung aus der Stufe und hält Grenzen ein", () => {
    const d = darstellungAus({ groesse: 40, tippflaeche_mm: 5, tempo: 9 }, "vorlesen");
    expect(d.groesse).toBe(40);
    expect(d.tippflaeche_mm).toBe(11.6);
    expect(d.tempo).toBe(1.5);
    expect(d.woerter_je_zeile).toBe(4);
    expect(d.vorlesen_von_selbst).toBe(true);
    expect(d.schrift).toContain("Andika");
    expect(darstellungAus({}, "vorlesen").tippflaeche_mm).toBe(20);
  });

  it("versteht die Schreibweise des Erwachsenenteils: Größen in Pixeln, Lesehilfen am Profil, Schriftgröße je Kind", () => {
    const ich = ichAus({
      profil: { id: "k2", rolle: "kind", stufe: "lesen_lernen", einstellungen: { lesehilfen: { silben: false, lesezeile: true, mitlesen: true, tempo: 0.8, schrift: "gross" } } },
      faehigkeiten: ["lesen", "vorlesen", "lesezeichen", "suche", "favoriten"],
      darstellung: { schrift: "andika", groesse_px: 25, woerter_je_zeile: null, tippflaeche_px: 76 },
    });
    expect(ich.darstellung.groesse).toBe(30);
    expect(ich.darstellung.woerter_je_zeile).toBe(0);
    expect(ich.darstellung.tippflaeche_mm).toBe(20.1);
    expect(ich.darstellung.silben).toBe(false);
    expect(ich.darstellung.tempo).toBe(0.8);
    expect(ich.darstellung.schrift).toContain("Andika");
    // Der Rückblick kommt mit den Lieblingen, solange der Server ihn nicht eigens nennt
    expect(ich.faehigkeiten.has("gelesen")).toBe(true);
    expect(faehigkeitenAus({ favoriten: true, gelesen: false }, "schule").has("gelesen")).toBe(false);
  });

  it("baut ein vollständiges Ich, auch aus wenig", () => {
    const ich = ichAus({ profil: { id: "k1", name: "Kim", rolle: "kind", stufe: "erstes_lesen" }, katze: { name: " Flocke " } });
    expect(ich.profil.stufe).toBe("erstes_lesen");
    expect(ich.profil.zeichen).toBe("face-smile");
    expect(ich.katze).toEqual({ an: true, name: "Flocke", schnurren: false });
    expect(ich.lesezeit).toEqual({ heute_s: 0, rest_s: null, ruht: false, ruhe_bis: null, ruhe_ab: null, hinweis_ab_s: null });
    expect(ich.darstellung.silben).toBe(true);
    expect(nutztKinderbereich(ich)).toBe(true);
    expect(nutztKinderbereich(ichAus({ profil: { rolle: "kind", stufe: "jugend" } }))).toBe(false);
    expect(nutztKinderbereich(ichAus({ profil: { rolle: "erwachsen" } }))).toBe(false);
  });

  it("liest Lesezeit und Katze tolerant", () => {
    expect(lesezeitAus({ heute_s: 90, rest_s: 10, ruht: true, ruhe_bis: "07:00", ruhe_von: "19:30", hinweis_ab_s: 300 })).toEqual({ heute_s: 90, rest_s: 10, ruht: true, ruhe_bis: "07:00", ruhe_ab: "19:30", hinweis_ab_s: 300 });
    expect(katzeAus({ an: false, schnurren: true })).toEqual({ an: false, name: "", schnurren: true });
  });
});

describe("Lesestand des Kinderlesers", () => {
  it("schreibt die Form des normalen Lesers und dazu Stelle, Lesezeichen und Ende", () => {
    const w = kinderlesewerte({ page: 3 }, { einheit: 2, zeichen: 40 }, { einheit: 1, zeichen: 0 }, false);
    const position = `pdf:${JSON.stringify(w)}`;
    expect(kindangabenAus(position)).toEqual({ einheit: 2, zeichen: 40, lesezeichen: { einheit: 1, zeichen: 0 }, fertig: false });
    expect(fertigGelesen(position, 10)).toBe(false);
    expect(fertigGelesen(`pdf:${JSON.stringify(kinderlesewerte({ page: 10 }, { einheit: 9, zeichen: 0 }, null, true))}`, 10)).toBe(true);
  });

  it("versteht Stände des normalen Lesers", () => {
    expect(kindangabenAus('epub:{"cfi":"epubcfi(/6/4!/4/2/1:0)","percent":40}')).toBeNull();
    expect(fertigGelesen("pdf:{\"page\":12}", 12)).toBe(true);
    expect(fertigGelesen('epub:{"percent":99.5}')).toBe(true);
    expect(fertigGelesen("")).toBe(false);
  });
});

describe("Textbücher", () => {
  it("teilt Absätze und Überschriften und beginnt an jeder Überschrift eine Einheit", () => {
    const s = textstueckeAus("# Erster Teil\n\nEin **kurzer** Satz.\n\n## Zweiter\n\nNoch [einer](x).", true);
    expect(s).toEqual([{ art: "titel", text: "Erster Teil" }, { art: "absatz", text: "Ein kurzer Satz." }, { art: "titel", text: "Zweiter" }, { art: "absatz", text: "Noch einer." }]);
    expect(einheitenAus(s).map((e) => e.length)).toEqual([2, 2]);
    expect(textstueckeAus("# Kein Titel\n\nText", false)[0].art).toBe("absatz");
  });
});
