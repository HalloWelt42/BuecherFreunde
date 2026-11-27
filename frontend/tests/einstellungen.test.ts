import { describe, expect, it } from "vitest";
import { reiterAus } from "../src/ansichten/einstellungen/reiter";
import { codeAusAnker, codeNormal, geraetename } from "../src/ansichten/anmeldung/kopplung";
import { alsHex, hexZuTon, tonZuHex } from "../src/lib/farbton";
import { findeSymbole, symbole } from "../src/lib/teile/symbole";

describe("Reiter der Einstellungen", () => {
  it("öffnet ohne Angabe die Darstellung", () => {
    expect(reiterAus("/settings")).toEqual({ reiter: "darstellung", stelle: "" });
    expect(reiterAus("/settings/gibtesnicht").reiter).toBe("darstellung");
  });

  it("führt alte Adressen an ihre Stelle", () => {
    expect(reiterAus("/settings/categories")).toEqual({ reiter: "regale", stelle: "regale" });
    expect(reiterAus("/settings/sammlungen")).toEqual({ reiter: "regale", stelle: "sammlungen" });
    expect(reiterAus("/settings/ai")).toEqual({ reiter: "mehr", stelle: "ki" });
    expect(reiterAus("/settings/system")).toEqual({ reiter: "wartung", stelle: "" });
    expect(reiterAus("/settings/legal")).toEqual({ reiter: "mehr", stelle: "rechtliches" });
  });

  it("kennt die neuen Adressen", () => {
    for (const r of ["darstellung", "verbindungen", "regale", "wartung", "mehr"]) expect(reiterAus(`/settings/${r}`)).toEqual({ reiter: r, stelle: "" });
  });
});

describe("Kopplung", () => {
  it("putzt den Code", () => {
    expect(codeNormal("ab12-cd34xyz")).toBe("AB12CD34");
    expect(codeAusAnker("#koppeln=ab12-cd34")).toBe("AB12CD34");
    expect(codeAusAnker("#anderes")).toBe("");
  });

  it("schlägt einen Gerätenamen vor", () => {
    expect(geraetename("Mozilla/5.0 (iPhone; CPU)", 5)).toBe("Telefon");
    expect(geraetename("Mozilla/5.0 (Macintosh)", 5)).toBe("Tablet");
    expect(geraetename("Mozilla/5.0 (Macintosh)", 0)).toBe("Rechner");
    expect(geraetename("Mozilla/5.0 (Linux; Android 14)", 5)).toBe("Tablet");
  });
});

describe("Farben", () => {
  it("erkennt Hexwerte", () => {
    expect(alsHex("#ABC")).toBe("#aabbcc");
    expect(alsHex("12ab9c")).toBe("#12ab9c");
    expect(alsHex("rot")).toBeNull();
  });

  it("rechnet Farbton und Hexwert ineinander um", () => {
    expect(hexZuTon("#ff0000")).toEqual({ ton: 0, saettigung: 100, helligkeit: 50 });
    expect(tonZuHex({ ton: 240, saettigung: 100, helligkeit: 50 })).toBe("#0000ff");
    expect(hexZuTon("#808080").saettigung).toBe(0);
    const { ton, saettigung, helligkeit } = hexZuTon(tonZuHex({ ton: 200, saettigung: 60, helligkeit: 40 }));
    expect(Math.abs(ton - 200)).toBeLessThanOrEqual(2);
    expect(Math.abs(saettigung - 60)).toBeLessThanOrEqual(2);
    expect(Math.abs(helligkeit - 40)).toBeLessThanOrEqual(1);
  });
});

describe("Symbole", () => {
  it("findet über deutsche Stichworte und über den Namen", () => {
    expect(findeSymbole("drache").map(([n]) => n)).toContain("fa-dragon");
    expect(findeSymbole("microchip").map(([n]) => n)).toContain("fa-microchip");
    expect(findeSymbole("")).toHaveLength(symbole.length);
  });

  it("führt jedes Zeichen einmal", () => {
    expect(new Set(symbole.map(([n]) => n)).size).toBe(symbole.length);
  });
});
