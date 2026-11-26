// Große Sammlungen als ein Eintrag, ihr eigenes Regal und Vorschläge (BF-66). Nur erfundene Titel und Namen.
import { render, screen } from "@testing-library/svelte";
import Band from "../src/ansichten/bibliothek/Band.svelte";
import Liste from "../src/ansichten/bibliothek/Liste.svelte";
import Regal from "../src/ansichten/bibliothek/Regal.svelte";
import Sammlungsband from "../src/ansichten/bibliothek/Sammlungsband.svelte";
import { stapellagen, zahlzeile } from "../src/ansichten/bibliothek/sammlungseintrag";
import { fundtext, kiSatz, umschlagreihe, wegSymbol } from "../src/ansichten/einstellungen/sammlungsvorschlaege.svelte";
import { grenzeAus } from "../src/ansichten/einstellungen/sammlungsgrenze";
import { autorenText, bandText, kurztitel, reihenkopf } from "../src/ansichten/sammlung/angaben";
import { navigate } from "../src/lib/router.svelte";
import { auswahl } from "../src/lib/stand/auswahl.svelte";
import { buecher } from "../src/lib/stand/buecher.svelte";
import { eintraegeAus, eintragsschluessel, fasstZusammen, verbindeSeiten } from "../src/lib/stand/eintraege";
import type { Buch, BuchListe, Eintrag, Sammlungseintrag } from "../src/lib/typen";

function buch(id: number, title: string, mehr: Partial<Buch> = {}): Buch {
  return {
    id, hash: "", title, author: "Jorin Sandvik", publisher: "", file_format: "epub", file_size: 1, cover_path: "", page_count: 0, year: null, isbn: "", typ: "", gattung: "",
    umschlag: "titelseite", umschlag_schlicht: false, umschlag_wahl: "", sammlung_id: null, band_nummer: "", is_favorite: false, is_to_read: false, rating: 0,
    reading_position: "", last_read_at: null, categories: [], sammlung: null, created_at: "", updated_at: "", ...mehr,
  };
}

const sternenfahrt: Sammlungseintrag = {
  id: 7, name: "Sternenfahrt", anzahl: 12, autor: "Jorin Sandvik",
  umschlaege: [buch(70, "Sternenfahrt 01 - Kalte Monde"), buch(71, "Sternenfahrt 02 - Glutwind"), buch(72, "Sternenfahrt 03 - Leere Häfen")],
};

const liste = (mehr: Partial<BuchListe>): BuchListe => ({ buecher: [], gesamt: 0, seite: 1, pro_seite: 48, seiten_gesamt: 1, ...mehr });

beforeEach(() => {
  navigate("/", true);
  auswahl.modus(false);
});

describe("Zusammenfassen: eine Stelle entscheidet", () => {
  it("fasst in Alle, Bücher, Dokumente und den Regalen zusammen", () => {
    expect(fasstZusammen([])).toBe(true);
    expect(fasstZusammen(["hat_isbn"])).toBe(true);
    expect(fasstZusammen(["category"])).toBe(true);
    expect(fasstZusammen(["category", "hat_isbn"])).toBe(true);
  });

  it("zeigt bei Suche, Weiterlesen, Favoriten, Lesesofa, Gelesen, Ungelesen und Markiertem jedes Buch", () => {
    for (const s of ["q", "weiterlesen", "is_favorite", "is_to_read", "gelesen", "hat_highlights"]) expect(fasstZusammen([s])).toBe(false);
    expect(fasstZusammen(["category", "q"])).toBe(false);
    expect(fasstZusammen(["sammlung"])).toBe(false);
  });

  it("fragt die Liste mit zusammenfassen nur in diesen Ansichten an", async () => {
    const adressen: string[] = [];
    globalThis.fetch = vi.fn((weg: string) => {
      adressen.push(weg);
      return Promise.resolve(new Response(JSON.stringify(liste({}))));
    }) as unknown as typeof fetch;
    navigate("/?category=3", true);
    await buecher.laden();
    navigate("/?is_favorite=true", true);
    await buecher.laden();
    navigate("/?gelesen=false", true);
    await buecher.laden();
    expect(adressen[0]).toContain("zusammenfassen=true");
    expect(adressen[1]).not.toContain("zusammenfassen");
    expect(adressen[2]).not.toContain("zusammenfassen");
  });

  it("blättert nach Einträgen und zählt die Bücher in Sammlungen", async () => {
    const eintraege: Eintrag[] = [{ art: "buch", buch: buch(1, "Nebelufer") }, { art: "sammlung", sammlung: sternenfahrt }];
    globalThis.fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(liste({ buecher: [buch(1, "Nebelufer")], eintraege, gesamt: 13, gesamt_eintraege: 2, in_sammlungen: 12, sammlungen_zusammengefasst: 1 }))))) as unknown as typeof fetch;
    navigate("/", true);
    await buecher.laden();
    expect(buecher.eintraege.map(eintragsschluessel)).toEqual(["b1", "s7"]);
    expect(buecher.liste.map((b) => b.id)).toEqual([1]);
    expect([buecher.gesamt, buecher.gesamtEintraege, buecher.inSammlungen, buecher.sammlungen]).toEqual([13, 2, 12, 1]);
    buecher.entferne(1);
    expect([buecher.gesamt, buecher.gesamtEintraege]).toEqual([12, 1]);
  });
});

describe("Einträge der Liste", () => {
  it("macht ohne zusammenfassen aus jedem Buch einen Eintrag", () => {
    expect(eintraegeAus(liste({ buecher: [buch(4, "Nebelufer")] }))).toEqual([{ art: "buch", buch: buch(4, "Nebelufer") }]);
  });

  it("unterscheidet Buch und Sammlung mit derselben Nummer und verbindet Seiten", () => {
    expect(eintragsschluessel({ art: "buch", buch: buch(7, "x") })).not.toBe(eintragsschluessel({ art: "sammlung", sammlung: sternenfahrt }));
    const eins = liste({ buecher: [buch(1, "a")], eintraege: [{ art: "buch", buch: buch(1, "a") }] });
    const zwei = liste({ buecher: [], eintraege: [{ art: "sammlung", sammlung: sternenfahrt }] });
    expect(verbindeSeiten([eins, zwei]).eintraege?.map(eintragsschluessel)).toEqual(["b1", "s7"]);
  });

  it("nennt Bücher und Sammlungen in der Zahlzeile", () => {
    expect(zahlzeile(4734, 105, 4)).toBe("4.734 Bücher, davon 105 in 4 Sammlungen");
    expect(zahlzeile(20, 12, 1)).toBe("20 Bücher, davon 12 in 1 Sammlung");
    expect(zahlzeile(1, 0, 0)).toBe("1 Buch");
  });
});

describe("Darstellung einer Sammlung als ein Band", () => {
  it("stapelt bis drei Umschläge wie im Entwurf", () => {
    const [a, b, c] = sternenfahrt.umschlaege;
    expect(stapellagen([a, b, c])).toEqual({ vorn: a, hinten: b, mitte: c });
    expect(stapellagen([a])).toEqual({ vorn: a, hinten: null, mitte: null });
  });

  it("zeigt Anzahl, Sammlung, Name, Autor und Bände und öffnet ihr Regal", () => {
    const { container } = render(Sammlungsband, { props: { sammlung: sternenfahrt } });
    const verweis = screen.getByRole("link", { name: "Sammlung Sternenfahrt, 12 Bände" });
    expect(verweis.getAttribute("href")).toBe("/collection/7");
    expect(container.querySelector(".anzahl")?.textContent).toBe("12");
    expect(screen.getByText("Sammlung")).toBeTruthy();
    expect(screen.getByText("Sternenfahrt")).toBeTruthy();
    expect(screen.getByText("Jorin Sandvik")).toBeTruthy();
    expect(screen.getByText("12 Bände")).toBeTruthy();
    expect([...container.querySelectorAll(".umschlagstapel > .umschlag")].map((u) => [...u.classList].filter((k) => k === "hinten" || k === "mitte").join(""))).toEqual(["hinten", "mitte", ""]);
  });

  it("ist im Bearbeitungsmodus nicht anhakbar und zählt nicht als Buch", () => {
    auswahl.modus(true);
    const eintraege: Eintrag[] = [{ art: "buch", buch: buch(1, "Nebelufer") }, { art: "sammlung", sammlung: sternenfahrt }];
    const { container } = render(Regal, { props: { eintraege, art: "grid" } });
    expect(screen.getByRole("button", { name: "Nebelufer" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sammlung Sternenfahrt, 12 Bände" })).toBeTruthy();
    expect([...container.querySelectorAll("[data-buch]")].map((k) => (k as HTMLElement).dataset.buch)).toEqual(["1"]);
    expect(container.querySelector("[data-sammlung] .haken")).toBeNull();
  });

  it("steht in der Liste als Zeile mit Bänden", () => {
    render(Liste, { props: { eintraege: [{ art: "sammlung", sammlung: sternenfahrt }] } });
    const zeile = screen.getByRole("link", { name: /Sternenfahrt/ });
    expect(zeile.getAttribute("href")).toBe("/collection/7");
    expect(zeile.textContent).toContain("12 Bände");
  });
});

describe("Eigenes Regal der Sammlung", () => {
  it("nimmt Reihennamen und Nummer aus dem Titel", () => {
    expect(kurztitel("Reihe 03 - Titel", ["Reihe"], "3")).toBe("Titel");
    expect(kurztitel("Sternenfahrt Band 12 - Kalte Monde", ["Sternenfahrt"], "12")).toBe("Kalte Monde");
    expect(kurztitel("Sternenfahrt 3. Das Original: Glutwind", ["Sternenfahrt"], "3")).toBe("Das Original: Glutwind");
    expect(kurztitel("Sternenfahrt: Leere Häfen", ["Sternenfahrt"])).toBe("Leere Häfen");
    expect(kurztitel("Kalte Monde (Sternenfahrt 12)", ["Sternenfahrt"], "12")).toBe("Kalte Monde");
  });

  it("erkennt ein Kürzel an der eigenen Bandnummer oder am Kopf der meisten Titel", () => {
    expect(kurztitel("SF 02 - Glutwind", ["Sternenfahrt"], "2")).toBe("Glutwind");
    expect(kurztitel("Station 7 - Ankunft", ["Sternenfahrt"], "2")).toBe("Station 7 - Ankunft");
    expect(kurztitel("Station 12 - Ankunft", ["Sternenfahrt"], "1")).toBe("Station 12 - Ankunft");
    // Nach dem Umstellen passt die Nummer im Titel nicht mehr zum Band; der Kopf der Reihe bleibt erkennbar
    const titel = ["SF 01 - Kalte Monde", "SF 02 - Glutwind", "SF 13 - Neue Ufer", "Sternenfahrt Band 4 - Eisige Wege"];
    expect(reihenkopf(titel)).toBe("SF");
    expect(kurztitel("SF 13 - Neue Ufer", ["Sternenfahrt", reihenkopf(titel)], "3")).toBe("Neue Ufer");
    expect(reihenkopf(["SF 01 - Kalte Monde", "Glutwind", "Leere Häfen"])).toBe("");
  });

  it("lässt andere Titel ganz und nimmt nie alles weg", () => {
    expect(kurztitel("Sternenfahrten im Nebel", ["Sternenfahrt"], "4")).toBe("Sternenfahrten im Nebel");
    expect(kurztitel("Sternenfahrt", ["Sternenfahrt"], "")).toBe("Sternenfahrt");
    expect(kurztitel("Nebelufer", [""], "")).toBe("Nebelufer");
  });

  it("schreibt Band und Autoren", () => {
    expect(bandText("3")).toBe("Band 3");
    expect(bandText(" ")).toBe("");
    const a = { author: "Jorin Sandvik" };
    const b = { author: "Ilka Morand" };
    expect(autorenText([a, b, a])).toBe("Jorin Sandvik und Ilka Morand");
    expect(autorenText([a, b, { author: "Tove Lindqvar" }])).toBe("Jorin Sandvik, Ilka Morand und Tove Lindqvar");
    expect(autorenText([a, b, { author: "C" }, { author: "D" }])).toBe("Jorin Sandvik, Ilka Morand, C und weitere");
    expect(autorenText([{ author: "" }])).toBe("");
  });

  it("zeigt auf dem Schild Band und Kurztitel, als Name bleibt der ganze Titel", () => {
    render(Band, { props: { buch: buch(71, "Sternenfahrt 02 - Glutwind", { band_nummer: "2" }), reihe: ["Sternenfahrt"] } });
    expect(screen.getByText("Band 2")).toBeTruthy();
    expect(screen.getByText("Glutwind")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sternenfahrt 02 - Glutwind" })).toBeTruthy();
    expect(screen.queryByText("EPUB")).toBeNull();
  });
});

describe("Vorschläge und Grenze", () => {
  it("zeigt bis neun Umschläge und den Rest als Zahl", () => {
    const zwoelf = Array.from({ length: 12 }, (_, n) => n);
    expect(umschlagreihe(zwoelf)).toEqual({ gezeigt: zwoelf.slice(0, 9), rest: 3 });
    expect(umschlagreihe([1, 2]).rest).toBe(0);
  });

  it("gibt Fundwegen der KI ihr Zeichen und macht ihren Satz erkennbar", () => {
    expect(wegSymbol("Reihe und Band im Titel bei 8 Büchern")).toBe("ruler-combined");
    expect(wegSymbol("Die KI nennt die Reihe Sternenfahrt")).toBe("robot");
    expect(kiSatz("eine Reihe, Name bestätigt")).toBe("KI: eine Reihe, Name bestätigt");
    expect(kiSatz("KI nicht erreichbar")).toBe("KI nicht erreichbar");
    expect(kiSatz(" ")).toBe("");
  });

  it("meldet die Zahl der Funde", () => {
    expect(fundtext(3)).toBe("3 Vorschläge für Sammlungen gefunden");
    expect(fundtext(1)).toBe("1 Vorschlag für Sammlungen gefunden");
    expect(fundtext(0)).toBe("Keine neuen Sammlungen gefunden");
  });

  it("nimmt als Grenze nur ganze Zahlen von 2 bis 1000", () => {
    expect(grenzeAus(8)).toBe(8);
    expect(grenzeAus("12")).toBe(12);
    for (const falsch of [1, 1001, 2.5, "", "acht", null]) expect(grenzeAus(falsch)).toBeNull();
  });
});
