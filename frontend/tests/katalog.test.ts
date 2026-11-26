// Katalog (BF-69): Filter der Leiste, Herkunft, Regeln, Entwurf, Einordnen, alte Regale, Kontrast der Zeichen, Bausteine.
// Nur erfundene Titel und Namen.
import { fireEvent, render, screen } from "@testing-library/svelte";
import Bereichskachel from "../src/ansichten/einstellungen/katalog/Bereichskachel.svelte";
import Regeln from "../src/ansichten/einstellungen/katalog/Regeln.svelte";
import Vorschlagszeile from "../src/ansichten/einstellungen/katalog/Vorschlagszeile.svelte";
import { altzeilen, zielVon } from "../src/ansichten/einstellungen/katalog/alte";
import { einordnen, grundzeilen, laufanteil, laufkopf, laufzahlen, mitAuch, stapeltext } from "../src/ansichten/einstellungen/katalog/einordnung.svelte";
import {
  entferneBereich, entferneKategorie, freierSchluessel, kuerzel, neuerKategorieschluessel, setzeBereich, setzeKategorie,
} from "../src/ansichten/einstellungen/katalog/entwurf";
import { einstellungAus } from "../src/ansichten/einstellungen/katalog/einstellungen";
import { betroffene } from "../src/ansichten/einstellungen/katalog/pflege.svelte";
import { reiterAus } from "../src/ansichten/einstellungen/reiter";
import { ZEICHENFARBE, kontrast, zeichenflaeche } from "../src/lib/farbton";
import {
  bereichBeruehrt, bereichGewaehlt, farbeVon, filternamen, findeKategorie, geltungstext, herkunftszeichen, istKatalogkategorie, kategorieWerte,
  legende, regelnAus, schalteBereich, schalteKategorie, sichtbareBereiche, trenneKategorien, umfang,
} from "../src/lib/katalog";
import { fasstZusammen } from "../src/lib/stand/eintraege";
import Katalogzeichen from "../src/lib/teile/Katalogzeichen.svelte";
import type { AltesRegal, Buch, Katalog, Katalogbereich, Katalogkategorie, Katalogvorschlag, Laufstand } from "../src/lib/typen";

const LEER = { sachgruppen: [], schlagworte: [], titelwoerter: [], verlage: [] };

function kategorie(id: number | undefined, schluessel: string, name: string, mehr: Partial<Katalogkategorie> = {}): Katalogkategorie {
  return { id, schluessel, name, zeichen: "book", farbe: "", ki_beschreibung: "", regeln: LEER, verborgen: false, herkunft: "standard", anzahl: 3, ...mehr };
}

function bereich(id: number | undefined, schluessel: string, name: string, kategorien: Katalogkategorie[], mehr: Partial<Katalogbereich> = {}): Katalogbereich {
  return { id, schluessel, name, zeichen: "folder", farbe: "#2f6fb3", beschreibung: "", arten: [""], verborgen: false, anzahl: 9, kategorien, ...mehr };
}

const technik = bereich(1, "technik", "Technik", [kategorie(11, "technik/funk", "Funk"), kategorie(12, "technik/uhren", "Uhrwerke"), kategorie(13, "technik/leer", "Leeres", { verborgen: true, anzahl: 0 })]);
const romane = bereich(2, "romane", "Romane", [kategorie(21, "romane/see", "Seegeschichten", { farbe: "#aa3355" })], { farbe: "#8e44ad" });
const katalog: Katalog = { bereiche: [technik, romane], regale: [], ohne_kategorie: 4, hat_katalog: true };

function buch(id: number, title: string): Buch {
  return {
    id, hash: "", title, author: "Edda Brannberg", publisher: "", file_format: "epub", file_size: 1, cover_path: "", page_count: 0, year: null, isbn: "", typ: "", gattung: "",
    umschlag: "gestaltet", umschlag_schlicht: false, umschlag_wahl: "", sammlung_id: null, band_nummer: "", is_favorite: false, is_to_read: false, rating: 0,
    reading_position: "", last_read_at: null, categories: [], sammlung: null, created_at: "", updated_at: "",
  };
}

const lauf = (mehr: Partial<Laufstand>): Laufstand => ({ laeuft: true, pause: false, stapel: 3, stapel_gesamt: 10, stapel_groesse: 500, regeln: 1874, ki: 912, ohne_vorschlag: 418, schritt: "", grund: "", ...mehr });

describe("Katalog in der Leiste", () => {
  it("ein Bereich steht für alle seine Kategorien, auch die verborgenen", () => {
    expect(kategorieWerte(technik)).toEqual(["11", "12", "13"]);
    expect(schalteBereich(technik, ["5"])).toEqual(["5", "11", "12", "13"]);
    expect(schalteBereich(technik, ["5", "11", "12", "13"])).toEqual(["5"]);
    expect(bereichGewaehlt(technik, ["11", "12", "13"])).toBe(true);
    expect(bereichGewaehlt(technik, ["11"])).toBe(false);
    expect(bereichBeruehrt(technik, ["12"])).toBe(true);
  });

  it("eine Kategorie grenzt einen ganz gewählten Bereich auf sich ein, sonst schaltet sie", () => {
    expect(schalteKategorie(technik, "12", ["5", "11", "12", "13"])).toEqual(["5", "12"]);
    expect(schalteKategorie(technik, "12", ["12"])).toEqual([]);
    expect(schalteKategorie(technik, "11", ["12"])).toEqual(["12", "11"]);
  });

  it("zeigt nur Sichtbares", () => {
    const sichtbar = sichtbareBereiche([technik, bereich(3, "aus", "Aus", [], { verborgen: true })]);
    expect(sichtbar.map((b) => b.name)).toEqual(["Technik"]);
    expect(sichtbar[0].kategorien.map((k) => k.name)).toEqual(["Funk", "Uhrwerke"]);
  });

  it("benennt die Überschrift nach Bereich, Kategorie und übrigen Regalen", () => {
    expect(filternamen(katalog, ["11", "12", "13", "21", "99"])).toEqual({ namen: ["Technik", "Seegeschichten"], uebrig: ["99"] });
    expect(filternamen(katalog, ["12"])).toEqual({ namen: ["Uhrwerke"], uebrig: [] });
    expect(filternamen(null, ["4"])).toEqual({ namen: [], uebrig: ["4"] });
  });

  it("findet Kategorien und ihre Farbe", () => {
    expect(findeKategorie(katalog, 21)?.bereich.name).toBe("Romane");
    expect(farbeVon(romane.kategorien[0], romane)).toBe("#aa3355");
    expect(farbeVon(technik.kategorien[0], technik)).toBe("#2f6fb3");
    expect(findeKategorie(katalog, 77)).toBeNull();
  });

  it("trennt Kategorien des Katalogs von Regalen am Buch", () => {
    expect(istKatalogkategorie({ id: 1, name: "Funk", art: "kategorie" })).toBe(true);
    expect(istKatalogkategorie({ id: 2, name: "Lieblingsstücke", art: "regal" })).toBe(false);
    expect(istKatalogkategorie({ id: 3, name: "Funk", bereich: "Technik" })).toBe(true);
    expect(istKatalogkategorie({ id: 4, name: "Alt" })).toBe(false);
    // Einträge der Bücherliste ohne Art erkennt der Katalog an der Nummer
    const { kategorien, regale } = trenneKategorien([{ id: 12, name: "Uhrwerke" }, { id: 4, name: "Lieblingsstücke" }, { id: 99, name: "Funk", art: "kategorie" }], katalog);
    expect(kategorien.map((k) => k.id)).toEqual([12, 99]);
    expect(regale.map((r) => r.id)).toEqual([4]);
  });

  it("fasst Sammlungen auch unter Ohne Kategorie zusammen", () => {
    expect(fasstZusammen(["ohne_kategorie"])).toBe(true);
  });
});

describe("Herkunft, Regeln, Geltung", () => {
  it("zeigt die Herkunft, verborgen geht vor", () => {
    expect(herkunftszeichen({ herkunft: "geteilt", verborgen: false })[0]).toBe("code-branch");
    expect(herkunftszeichen({ herkunft: "neu", verborgen: true })[0]).toBe("eye-slash");
    expect(herkunftszeichen({ herkunft: "", verborgen: false })[1]).toBe("selbst angelegt");
  });

  it("nennt in der Legende selbst Angelegtes nur, wo es vorkommt", () => {
    expect(legende([technik]).map(([, t]) => t)).toEqual(["aus dem Standard", "geteilt, weil groß", "neu aus dem Bestand", "verborgen, ohne Bücher"]);
    expect(legende([bereich(1, "a", "A", [kategorie(1, "a/b", "B", { herkunft: "eigen" })])]).map(([, t]) => t)).toContain("selbst angelegt");
  });

  it("macht aus allem vier saubere Listen", () => {
    expect(regelnAus({ schlagworte: [" Funk ", "Funk", ""], titelwoerter: undefined } as never)).toEqual({ ...LEER, schlagworte: ["Funk"] });
    expect(regelnAus(null)).toEqual(LEER);
  });

  it("sagt knapp, wofür ein Bereich gilt, wenn nicht für Bücher", () => {
    const name = (a: string) => ({ dokument: "Dokument", heft: "Heft" })[a] ?? a;
    expect(geltungstext(["dokument", "heft"], name)).toBe("gilt für Dokument, Heft");
    expect(geltungstext(["", "heft"], name)).toBe("");
    expect(geltungstext([], name)).toBe("");
    expect(umfang([technik, romane])).toEqual({ bereiche: 2, kategorien: 4 });
  });
});

describe("Entwurf ändern", () => {
  const entwurf = [bereich(undefined, "technik", "Technik", [kategorie(undefined, "technik/funk", "Funk"), kategorie(undefined, "technik/uhren", "Uhrwerke")]), bereich(undefined, "romane", "Romane", [])];

  it("bildet freie Schlüssel ohne Umlaute", () => {
    expect(kuerzel("Bücher über Größe")).toBe("buecher-ueber-groesse");
    expect(kuerzel("!!")).toBe("neu");
    expect(freierSchluessel("a", new Set(["a", "a-2"]))).toBe("a-3");
    expect(neuerKategorieschluessel(entwurf, "technik", "Funk")).toBe("technik/funk-2");
  });

  it("ändert an derselben Stelle und verschiebt ans Ende eines anderen Bereichs", () => {
    const anders = setzeKategorie(entwurf, "technik/funk", "technik", kategorie(undefined, "technik/funk", "Funk und Radio"));
    expect(anders[0].kategorien.map((k) => k.name)).toEqual(["Funk und Radio", "Uhrwerke"]);
    const verschoben = setzeKategorie(entwurf, "technik/funk", "romane", kategorie(undefined, "technik/funk", "Funk"));
    expect(verschoben[0].kategorien.map((k) => k.name)).toEqual(["Uhrwerke"]);
    expect(verschoben[1].kategorien.map((k) => k.name)).toEqual(["Funk"]);
    expect(setzeKategorie(entwurf, null, "romane", kategorie(undefined, "romane/neu", "Neu"))[1].kategorien).toHaveLength(1);
    expect(entwurf[0].kategorien).toHaveLength(2);
  });

  it("legt Bereiche an, ändert sie mit ihren Kategorien und entfernt", () => {
    const { kategorien: _k, ...kopf } = entwurf[0];
    expect(setzeBereich(entwurf, "technik", { ...kopf, name: "Werkstatt" })[0]).toMatchObject({ name: "Werkstatt", kategorien: entwurf[0].kategorien });
    expect(setzeBereich(entwurf, null, { ...kopf, schluessel: "neu", name: "Neu" }).map((b) => b.name)).toEqual(["Technik", "Romane", "Neu"]);
    expect(entferneBereich(entwurf, "romane").map((b) => b.name)).toEqual(["Technik"]);
    expect(entferneKategorie(entwurf, "technik/uhren")[0].kategorien.map((k) => k.name)).toEqual(["Funk"]);
  });
});

describe("Einordnen", () => {
  it("zeigt den Stapel, an dem gearbeitet wird; der Server zählt fertige", () => {
    expect(stapeltext(lauf({}))).toBe("Stapel 4 von 10, je 500 Titel");
    expect(stapeltext(lauf({ laeuft: false, stapel: 10 }))).toBe("Stapel 10 von 10, je 500 Titel");
    expect(stapeltext(lauf({ stapel_gesamt: 0 }))).toBe("");
    expect(laufanteil(lauf({}))).toBeCloseTo(0.3);
    expect(laufzahlen(lauf({}))).toBe("Regeln: 1.874 Vorschläge, KI: 912 Vorschläge, 418 Bücher ohne Vorschlag");
    expect(laufkopf(lauf({ pause: true }))).toBe("Einordnen macht Pause");
    expect(laufkopf(lauf({ laeuft: false }))).toBe("Einordnen fertig");
  });

  it("zeigt Gründe als knappe Zeilen mit dem Zeichen ihrer Quelle", () => {
    expect(grundzeilen({ quelle: "beide", gruende: ["Sachgruppe 621", "KI: Fachbuch über Funktechnik"] })).toEqual([
      { symbol: "ruler-combined", text: "Sachgruppe 621" },
      { symbol: "robot", text: "Fachbuch über Funktechnik" },
    ]);
    expect(grundzeilen({ quelle: "ki", gruende: ["Erzählung am Meer"] })[0].symbol).toBe("robot");
    expect(grundzeilen({ quelle: "regel", gruende: ["Titel enthält Funk"] })[0].symbol).toBe("ruler-combined");
  });

  it("nimmt ein gewähltes auch mit an", () => {
    const v = (id: number, auch: Katalogvorschlag["auch"]): Katalogvorschlag => ({ id, buch: buch(id, "Wellen über dem Deich"), kategorie_id: 11, quelle: "ki", gruende: [], sicherheit: 70, vorab: false, auch });
    const liste = [v(1, [{ kategorie_id: 12, name: "Uhrwerke", sicherheit: 88, id: 7 }]), v(2, [{ kategorie_id: 12, name: "Uhrwerke", sicherheit: 60, id: 8 }])];
    expect(mitAuch(liste, [1, 2], new Set([1]))).toEqual([1, 2, 7]);
    expect(mitAuch(liste, [2], new Set([1, 2]))).toEqual([2, 8]);
    expect(mitAuch(liste, [1], new Set())).toEqual([1]);
  });

  it("zeigt eine Vorschlagszeile mit Haken, Gründen, auch und Sicherheit", async () => {
    const v: Katalogvorschlag = {
      id: 5, buch: buch(40, "Funkstille am Leuchtturm"), kategorie_id: 11, quelle: "beide", gruende: ["Schlagwort Funk", "KI: Roman über einen Funker"], sicherheit: 93, vorab: true,
      auch: [{ kategorie_id: 21, name: "Seegeschichten", sicherheit: 81, id: 9 }],
    };
    render(Vorschlagszeile, { props: { vorschlag: v } });
    expect(screen.getByText("Funkstille am Leuchtturm")).toBeTruthy();
    expect(screen.getByText("Schlagwort Funk")).toBeTruthy();
    expect(screen.getByText("Roman über einen Funker")).toBeTruthy();
    expect(screen.getByText("93 %")).toBeTruthy();
    const auch = screen.getByRole("button", { name: /auch: Seegeschichten, 81 %/ });
    expect(auch.getAttribute("aria-pressed")).toBe("false");
    await fireEvent.click(auch);
    expect(einordnen.auch.has(5)).toBe(true);
    await fireEvent.click(screen.getByRole("checkbox", { name: "Funkstille am Leuchtturm auswählen" }));
    expect(einordnen.angehakt.has(5)).toBe(true);
  });
});

describe("Kategorien aus Importen", () => {
  const alt = (id: number, name: string, art: "kategorie" | "schlagwort", kategorie_id: number | null): AltesRegal => ({ id, name, anzahl: 1, vorschlag: { art, kategorie_id, grund: art === "schlagwort" ? "Sprache, keine Kategorie" : "" } });
  const alte = [alt(1, "Seefahrt", "kategorie", 21), alt(2, "Sea stories", "kategorie", 21), alt(3, "Norwegisch", "schlagwort", null), alt(4, "Funkwesen", "kategorie", 11), alt(5, "Rätsel", "kategorie", null)];

  it("fasst alte Regale je Ziel zusammen, in der Reihenfolge des Katalogs", () => {
    const zeilen = altzeilen(alte, katalog, new Map());
    expect(zeilen.map((z) => [z.name, z.alte.map((a) => a.name)])).toEqual([
      ["Funk", ["Funkwesen"]],
      ["Seegeschichten", ["Seefahrt", "Sea stories"]],
      ["Schlagwort am Buch", ["Norwegisch"]],
      ["Noch ohne Ziel", ["Rätsel"]],
    ]);
    expect(zeilen[1]).toMatchObject({ unter: "Romane", farbe: "#aa3355" });
    expect(zeilen[2].unter).toBe("Sprache, keine Kategorie");
  });

  it("nimmt die eigene Wahl vor dem Vorschlag", () => {
    const gewaehlt = new Map([[3, { kategorie_id: 12 }]]);
    expect(zielVon(alte[2], gewaehlt)).toEqual({ kategorie_id: 12 });
    expect(altzeilen(alte, katalog, gewaehlt).find((z) => z.name === "Uhrwerke")?.alte.map((a) => a.name)).toEqual(["Norwegisch"]);
  });
});

describe("Zeichen im Katalog", () => {
  // Der Standard-Katalog des Servers, für jede Bibliothek (backend/app/katalog/standard.json)
  const roh = Object.values(import.meta.glob<string>("../../backend/app/katalog/standard.json", { query: "?raw", import: "default", eager: true }))[0];
  const standard = JSON.parse(roh) as { bereiche: { farbe: string }[] };
  const auswahl = ["#ef4444", "#f43f5e", "#ec4899", "#d946ef", "#a855f7", "#8b5cf6", "#6366f1", "#3b82f6", "#0ea5e9", "#06b6d4", "#14b8a6", "#10b981",
    "#22c55e", "#84cc16", "#eab308", "#f59e0b", "#f97316", "#fb923c", "#78716c", "#a8a29e", "#6b7280", "#9ca3af", "#374151", "#111827", "#ffffff", "#ffff00"];

  it("erreicht für jede Farbe des Standards und der Farbwahl mindestens 4,5 : 1", () => {
    const farben = [...standard.bereiche.map((b) => b.farbe), ...auswahl];
    expect(standard.bereiche.length).toBeGreaterThan(0);
    for (const f of farben) expect(kontrast(ZEICHENFARBE, zeichenflaeche(f)), f).toBeGreaterThanOrEqual(4.5);
  });

  it("dunkelt immer ab und hält den Farbton", () => {
    expect(zeichenflaeche("#000000")).toBe("#000000");
    const [r, g, b] = [1, 3, 5].map((n) => Number.parseInt(zeichenflaeche("#2f6fb3").slice(n, n + 2), 16));
    expect(b).toBeGreaterThan(g);
    expect(g).toBeGreaterThan(r);
    expect(kontrast("#ffffff", "#000000")).toBeCloseTo(21);
  });

  it("setzt die Fläche als Wert am Zeichen", () => {
    const { container } = render(Katalogzeichen, { props: { name: "microchip", farbe: "#eab308", groesse: "gross" } });
    const z = container.querySelector(".katalogzeichen") as HTMLElement;
    expect(z.classList.contains("gross")).toBe(true);
    expect(z.style.getPropertyValue("--zf")).toBe(zeichenflaeche("#eab308"));
    expect(z.querySelector("i")?.classList.contains("fa-microchip")).toBe(true);
  });
});

describe("Bausteine des Reiters", () => {
  it("führt /settings/katalog zum Reiter", () => {
    expect(reiterAus("/settings/katalog")).toEqual({ reiter: "katalog", stelle: "" });
  });

  it("nimmt Einstellungen nur als ganze Zahlen in den Grenzen des Servers", () => {
    expect(einstellungAus("stapel", "500")).toBe(500);
    expect(einstellungAus("stapel", 20_001)).toBeNull();
    expect(einstellungAus("sicher_ab", 0)).toBe(0);
    expect(einstellungAus("sicher_ab", 101)).toBeNull();
    expect(einstellungAus("ki_je_anfrage", 2.5)).toBeNull();
    expect(einstellungAus("teilen_ab", "")).toBeNull();
  });

  it("nennt in der Folgenvorschau die ersten betroffenen Bücher", () => {
    expect(betroffene(["Nebelufer", "Kupferzeit"], 12)).toEqual(["Betroffen: Nebelufer, Kupferzeit und 10 weitere."]);
    expect(betroffene(["Nebelufer"], 1)).toEqual(["Betroffen: Nebelufer."]);
    expect(betroffene([], 0)).toEqual([]);
  });

  it("zeigt eine Bereichskachel mit Herkunft, Zahl und Geltung", async () => {
    const besonderes = bereich(4, "besonderes", "Besonderes", [kategorie(41, "besonderes/zettel", "Zettel", { herkunft: "neu", anzahl: 12 })], { arten: ["dokument"], beschreibung: "Alles außer Büchern" });
    const offen = vi.fn();
    render(Bereichskachel, { props: { bereich: besonderes, onbereich: () => {}, onkategorie: offen, onneu: () => {}, onziehen: () => {}, onueber: () => {}, onablegen: () => {} } });
    expect(screen.getByText("Alles außer Büchern")).toBeTruthy();
    expect(screen.getByText(/gilt für/)).toBeTruthy();
    expect(screen.getByText("neu aus dem Bestand")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: /Zettel/ }));
    expect(offen).toHaveBeenCalledWith(besonderes.kategorien[0]);
  });

  it("verborgene Bereiche zeigen keine Kategorien", () => {
    const aus = bereich(5, "aus", "Comics", [kategorie(51, "aus/a", "Hefte")], { verborgen: true, anzahl: 0 });
    render(Bereichskachel, { props: { bereich: aus, onbereich: () => {}, onkategorie: () => {}, onneu: () => {}, onziehen: () => {}, onueber: () => {}, onablegen: () => {} } });
    expect(screen.getByText("keine Bücher, verborgen")).toBeTruthy();
    expect(screen.queryByText("Hefte")).toBeNull();
  });

  it("ändert Regeln: Wert dazu, Wert weg, Regel dazu", async () => {
    let regeln = { ...LEER, schlagworte: ["Funk"] };
    const aendern = vi.fn((r) => (regeln = r));
    const { rerender } = render(Regeln, { props: { regeln, gespeichert: regeln, treffer: { regeln: [{ art: "schlagworte", werte: ["Funk"], treffer: 41 }], zusammen: 41, ki_vorschlaege: 3 }, onaendern: aendern } });
    expect(screen.getByText("41")).toBeTruthy();
    expect(screen.getByText("zusammen 41 Bücher, dazu 3 Vorschläge der KI")).toBeTruthy();
    await fireEvent.click(screen.getByRole("button", { name: "Wert dazu" }));
    const feld = screen.getByRole("textbox", { name: "Neuer Wert: Schlagwort" });
    await fireEvent.input(feld, { target: { value: "Radio" } });
    await fireEvent.keyDown(feld, { key: "Enter" });
    expect(aendern).toHaveBeenLastCalledWith({ ...LEER, schlagworte: ["Funk", "Radio"] });
    await rerender({ regeln, gespeichert: { ...LEER, schlagworte: ["Funk"] }, treffer: null, onaendern: aendern });
    await fireEvent.click(screen.getByRole("button", { name: "Funk entfernen" }));
    expect(aendern).toHaveBeenLastCalledWith({ ...LEER, schlagworte: ["Radio"] });
    await fireEvent.click(screen.getByRole("button", { name: "Regel" }));
    await fireEvent.click(screen.getByRole("button", { name: "Verlag" }));
    expect(screen.getByRole("textbox", { name: "Neuer Wert: Verlag" })).toBeTruthy();
  });
});
