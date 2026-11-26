import { describe, expect, it } from "vitest";
import { aenderungen, anfangsbuchstaben, formularVon, imBestand, lebensdaten, pruefe, schriftAuf, uebernahmefelder, verweistext, vergleichszeilen } from "../src/ansichten/autoren/angaben";
import { betroffen, regalwerte } from "../src/ansichten/hinzu/quellen/ergaenzung";
import type { Anreicherung, Autoreneinzeln } from "../src/lib/api/authors";

const autor: Autoreneinzeln = {
  id: 5, name: "Theodor Fontane", photo_path: "", birth_year: 1819, death_year: null, nationality: "", biography: "", beschreibung: "Erzähler", wikidata_id: "", wikipedia_url: "", website: "", quelle: "", konfidenz: "", score: 0, books: [], werke: [], verweise: [],
};

describe("Autoren: Angaben", () => {
  it("nennt Lebensdaten nur, wenn es welche gibt", () => {
    expect(lebensdaten({ birth_year: null, death_year: null })).toBe("");
    expect(lebensdaten({ birth_year: 1819, death_year: null })).toBe("geboren 1819");
    expect(lebensdaten({ birth_year: null, death_year: 1898 })).toBe("unbekannt bis 1898");
    expect(lebensdaten({ birth_year: -427, death_year: -347 })).toBe("427 v. Chr. bis 347 v. Chr.");
  });

  it("nimmt zwei Anfangsbuchstaben und lesbare Schrift", () => {
    expect(anfangsbuchstaben("J. W. von Goethe")).toBe("JW");
    expect(schriftAuf("#f4efe2")).not.toBe(schriftAuf("#0e2b2b"));
  });

  it("prüft Jahre und Website", () => {
    const f = formularVon(autor);
    expect(pruefe(f, 2026)).toEqual({});
    expect(pruefe({ ...f, birth_year: "18xx" }, 2026)).toHaveProperty("birth_year");
    expect(pruefe({ ...f, death_year: "1800" }, 2026)).toHaveProperty("death_year");
    expect(pruefe({ ...f, death_year: "2300" }, 2026)).toHaveProperty("death_year");
    expect(pruefe({ ...f, website: "fontane" }, 2026)).toHaveProperty("website");
    expect(pruefe({ ...f, name: " " }, 2026)).toHaveProperty("name");
  });

  it("schickt nur Geändertes und leert Jahre mit null", () => {
    const f = formularVon(autor);
    expect(aenderungen(autor, f)).toEqual({});
    expect(aenderungen(autor, { ...f, birth_year: "", nationality: "Deutschland " })).toEqual({ birth_year: null, nationality: "Deutschland" });
  });
});

describe("Autoren: Vergleich", () => {
  const antwort: Anreicherung = {
    angereichert: true,
    vorschlag: { name: "Theodor Fontane", beschreibung: "Deutscher Schriftsteller", birth_year: 1819, death_year: 1898, photo_url: "http://bild", konfidenz: "hoch", score: 42, werke: [{ titel: "Effi Briest" }] },
    aktuell: { name: "Theodor Fontane", birth_year: 1819, death_year: null, hat_foto: false },
  };

  it("sperrt Gleiches, wählt Neues und nimmt fehlende Vergleichswerte vom Autor", () => {
    const zeilen = vergleichszeilen(autor, antwort, "/foto");
    const nach = (k: string) => zeilen.find((z) => z.schluessel === k)!;
    expect(nach("name").gleich).toBe(true);
    expect(nach("birth_year").gleich).toBe(true);
    expect(nach("death_year")).toMatchObject({ gleich: false, gewaehlt: true, neu: "1898" });
    expect(nach("beschreibung").alt).toBe("Erzähler");
    expect(nach("photo_url")).toMatchObject({ bildAlt: undefined, bildNeu: "http://bild" });
  });

  it("sendet die Beschreibung nur, wenn sie gewählt ist", () => {
    const zeilen = vergleichszeilen(autor, antwort, "/foto");
    const ohne = zeilen.map((z) => (z.schluessel === "beschreibung" ? { ...z, gewaehlt: false } : z));
    expect(uebernahmefelder(antwort.vorschlag!, zeilen)).toHaveProperty("beschreibung");
    const felder = uebernahmefelder(antwort.vorschlag!, ohne);
    expect(felder).not.toHaveProperty("beschreibung");
    expect(felder).not.toHaveProperty("name");
    expect(felder).toMatchObject({ death_year: 1898, konfidenz: "hoch", score: 42 });
  });

  it("zeigt Verweise auf Normdateien als eine Zeile und sendet sie nur gewählt", () => {
    expect(verweistext({ viaf: "59157273", gnd: "115673784", fremd: "x" })).toBe("GND 115673784, VIAF 59157273");
    const mit: Anreicherung = { ...antwort, vorschlag: { ...antwort.vorschlag, verweise: { gnd: "115673784" } }, aktuell: { ...antwort.aktuell, verweise: {} } };
    const zeilen = vergleichszeilen(autor, mit, "/foto");
    expect(zeilen.find((z) => z.schluessel === "verweise")).toMatchObject({ alt: "", neu: "GND 115673784", gewaehlt: true });
    expect(uebernahmefelder(mit.vorschlag!, zeilen).verweise).toEqual({ gnd: "115673784" });
    const schon = { ...mit, aktuell: { ...mit.aktuell, verweise: { gnd: "115673784" } } };
    expect(vergleichszeilen(autor, schon, "/foto").find((z) => z.schluessel === "verweise")?.gleich).toBe(true);
  });

  it("erkennt Werke im Bestand in beide Richtungen", () => {
    expect(imBestand("Effi Briest", [{ title: "Effi Briest, Roman" }])).toBe(true);
    expect(imBestand("Der Stechlin, Roman", [{ title: "Der Stechlin" }])).toBe(true);
    expect(imBestand("Irrungen", [{ title: "Effi Briest" }])).toBe(false);
  });
});

describe("Ergänzung", () => {
  it("zählt Volltext und Bücher ohne Regal mit", () => {
    const v = { gesamt: 3, typen: { cover: 3, volltext: 20 } };
    expect(betroffen(v, ["cover"], null, [])).toBe(3);
    expect(betroffen(v, ["cover", "volltext"], null, [])).toBe(20);
    expect(betroffen({ gesamt: 0, typen: {} }, ["cover"], 0, [{ id: null, name: "Ohne Kategorie", anzahl: 4 }])).toBe(4);
    expect(betroffen(v, [], null, [])).toBe(0);
    expect(regalwerte([{ id: null, name: "x", anzahl: 4 }])).toEqual([["", "Alle Regale"], ["0", "Ohne Regal (4)"]]);
  });
});
