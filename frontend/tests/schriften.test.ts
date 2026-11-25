import { GRUPPEN, LESESCHRIFTEN, gleicheSchrift, schriftCss, schriftZu } from "../src/lib/leser/schriften";

describe("Leseschriften", () => {
  it("sind eine Liste in drei Gruppen, mit Schnitten 400, kursiv und 700, wo die Schrift sie hat", () => {
    expect(LESESCHRIFTEN.length).toBe(12);
    expect(new Set(LESESCHRIFTEN.map((s) => s.gruppe))).toEqual(new Set(GRUPPEN));
    for (const s of LESESCHRIFTEN.filter((x) => x.schnitte.length)) {
      expect(s.schnitte.map(([g, st]) => `${g}${st}`)).toContain("400normal");
      expect(s.schnitte.map(([g, st]) => `${g}${st}`)).toContain("700normal");
    }
  });

  it("kennen die früher gemerkten Kennungen und Schreibweisen", () => {
    for (const k of ["literata", "atkinson", "barlow", "jetbrains", "georgia", "system"]) expect(LESESCHRIFTEN.some((s) => s.kennung === k)).toBe(true);
    expect(schriftZu("Literata, serif")?.kennung).toBe("literata");
    expect(gleicheSchrift("'JetBrains Mono', monospace", '"JetBrains Mono"')).toBe(true);
  });

  it("geben einem Kapitelrahmen nur die gewählte Schrift mit", () => {
    const css = schriftCss('"Vollkorn", Georgia, serif');
    expect(css.match(/@font-face/g)?.length).toBe(3);
    expect(css).not.toContain("Literata");
    expect(schriftCss("Georgia, serif")).toBe("");
  });
});
