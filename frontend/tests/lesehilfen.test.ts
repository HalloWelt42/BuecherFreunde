import { streifenUm } from "../src/lib/leser/fokus";
import { hilfenCss, hilfenEpubCss, lesehilfen, MITGELIEFERT, OHNE } from "../src/lib/leser/lesehilfen.svelte";

describe("Fokus", () => {
  it("legt vier Streifen um das Fenster, das Fenster bleibt ganz frei", () => {
    const s = streifenUm({ links: 100, oben: 200, rechts: 500, unten: 260 }, 800, 600, 48);
    expect(s.map((x) => [x.rand, x.links, x.oben, x.breite, x.hoehe])).toEqual([
      ["unten", 0, 0, 800, 200], ["oben", 0, 260, 800, 340], ["rechts", 0, 200, 100, 60], ["links", 500, 200, 300, 60],
    ]);
  });

  it("bleibt in der Fläche, auch wenn das Fenster hinausragt", () => {
    const s = streifenUm({ links: -50, oben: -10, rechts: 900, unten: 700 }, 800, 600, 0);
    expect(s.every((x) => x.breite >= 0 && x.hoehe >= 0 && x.oben + x.hoehe <= 600)).toBe(true);
  });
});

describe("Lesehilfen", () => {
  it("speichern, benennen und löschen eigene Voreinstellungen, die mitgelieferten bleiben", () => {
    expect(lesehilfen.speichere("Tag", "#000", "#fff")).toBeNull();
    lesehilfen.setzeHilfen({ waerme: 20 });
    expect(lesehilfen.speichere("Mein Abend", "#111111", "#eeeeee")?.hilfen.waerme).toBe(20);
    lesehilfen.merkeFuerBuch(7, "Mein Abend");
    expect(lesehilfen.benenne("Mein Abend", "Nacht")).toBe(false);
    expect(lesehilfen.benenne("Mein Abend", "Spät")).toBe(true);
    expect([lesehilfen.fuerBuch(7)?.name, lesehilfen.buecherMit("Spät")]).toEqual(["Spät", 1]);
    lesehilfen.loesche("Spät");
    expect([lesehilfen.voreinstellungen.length, lesehilfen.fuerBuch(7)]).toEqual([MITGELIEFERT.length, undefined]);
    expect(JSON.parse(localStorage.getItem("leser.hilfen")!).eigene).toEqual([]);
  });

  it("werden zu CSS, und ohne Änderung bleibt alles, wie es war", () => {
    expect(hilfenCss(OHNE)["--hilfe-filter"]).toBe("none");
    expect(hilfenEpubCss(OHNE)).toBe("");
    const v = hilfenCss({ ...OHNE, helligkeit: 90, waerme: 25, ausrichtung: "block", trennung: false });
    expect([v["--hilfe-filter"], v["--hilfe-ausrichtung"], v["--hilfe-trennung"]]).toEqual(["brightness(0.9) sepia(0.25)", "justify", "manual"]);
    expect(hilfenEpubCss({ ...OHNE, bilder: 70, zeichen: 5 })).toContain("letter-spacing: 0.05em");
  });
});
