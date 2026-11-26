// BF-59: gestaltete Deckblätter. Maskieren, Zuordnung je Art und Gattung, Titel bleiben im Feld; der Umschlag zeigt
// das Blatt oder das Bild je nach Angabe des Servers. Dazu die Grenzfälle aus BF-51 (lange Wörter, volle Breite, leer).
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import Buchkopf from "../src/ansichten/buch/Buchkopf.svelte";
import { arten } from "../src/lib/stand/arten.svelte";
import Umschlag from "../src/lib/teile/Umschlag.svelte";
import type { BuchEinzeln } from "../src/lib/typen";
import { blattFarben, gestaltetesBlatt, gestaltung, type Blattangaben } from "../src/lib/umschlag/gestaltet";
import { MUSTER } from "../src/lib/umschlag/muster";
import { blockhoehe, gekuerzt, laenge, maskiere, passe, setze } from "../src/lib/umschlag/satz";

const GATTUNGEN = ["krimi", "thriller", "historisch", "fantasy", "liebesroman", "roman", "klassiker", "sachbuch", "ratgeber", "informatik", "mathematik", "fachbuch", "wirtschaft"];
const ARTEN = ["dokument", "heft", "katalog", "broschuere"];

/** Jede Gestalt, die es gibt: alle Arten, alle Gattungen, ohne Gattung */
const alleGestalten = (b: Omit<Blattangaben, "typ" | "gattung">): Blattangaben[] => [
  ...ARTEN.map((typ) => ({ ...b, typ })),
  ...GATTUNGEN.map((gattung) => ({ ...b, gattung })),
  { ...b, gattung: "" },
];

function lies(svg: string): Document {
  const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
  expect(doc.querySelector("parsererror")).toBeNull();
  return doc;
}

const texte = (svg: string): string[] => [...lies(svg).querySelectorAll("text")].map((t) => t.textContent ?? "");

describe("Maskieren", () => {
  it("setzt die fünf Zeichen von XML um und nimmt verbotene Steuerzeichen heraus", () => {
    expect(maskiere(`a & b < c > d " e ' f\u0001`)).toBe("a &amp; b &lt; c &gt; d &quot; e &apos; f");
  });

  it("Titel und Autor mit Markup bleiben Text, in jedem Muster", () => {
    const boese = { id: 7, title: `</text><script> & "Zitat" 'x'`, author: `<img src=x onerror="alert(2)">`, year: 2020 };
    for (const b of alleGestalten(boese)) {
      const svg = gestaltetesBlatt(b);
      expect(svg).not.toContain("<script");
      expect(svg).not.toContain("<img");
      const doc = lies(svg);
      expect(doc.querySelectorAll("script, img, foreignObject").length).toBe(0);
      expect(texte(svg).join(" ")).toContain("</text><script>");
    }
  });

  it("keine Kennungen und keine Verweise darauf: viele Blätter auf einer Seite stören sich nicht", () => {
    for (const b of alleGestalten({ id: 3, title: "Ein Titel", author: "Jemand", year: 2001 })) {
      const svg = gestaltetesBlatt(b);
      expect(svg).not.toMatch(/\sid="/);
      expect(svg).not.toContain("url(#");
      expect(svg).toMatch(/^<svg [^>]*viewBox="0 0 200 300"/);
    }
  });
});

describe("Zuordnung", () => {
  it("Arten haben ihr eigenes Muster, auch mit Gattung", () => {
    expect(gestaltung({ id: 1, title: "", typ: "dokument", gattung: "krimi" }).muster).toBe("ordnerRuecken");
    expect(gestaltung({ id: 1, title: "", typ: "heft" }).muster).toBe("heft");
    expect(gestaltung({ id: 1, title: "", typ: "katalog" }).muster).toBe("katalog");
    expect(gestaltung({ id: 1, title: "", typ: "broschuere" }).muster).toBe("broschuere");
  });

  it("Bücher nach Gattung, ohne oder mit unbekannter Gattung nur Schrift", () => {
    const muster = Object.fromEntries(GATTUNGEN.map((gattung) => [gattung, gestaltung({ id: 1, title: "", gattung }).muster]));
    expect(muster).toEqual({
      krimi: "teilung", thriller: "kreis", historisch: "leinen", fantasy: "sterne", liebesroman: "wellen", roman: "berge", klassiker: "typo",
      sachbuch: "globus", ratgeber: "blatt", informatik: "schaltung", mathematik: "raster", fachbuch: "kreis", wirtschaft: "teilung",
    });
    const ohne = gestaltung({ id: 1, title: "" });
    expect(ohne.muster).toBe("typo");
    for (const fremd of ["unbekannt", "constructor", "__proto__", "toString"]) expect(gestaltung({ id: 1, title: "", gattung: fremd, typ: fremd })).toEqual(ohne);
    expect(ohne.farben).not.toEqual(gestaltung({ id: 1, title: "", gattung: "klassiker" }).farben);
  });

  it("mehrere Farbsätze wechseln nach der Nummer, ein Buch behält seinen", () => {
    const historisch = (id: number) => blattFarben({ id, title: "", gattung: "historisch" });
    expect(historisch(1)).not.toEqual(historisch(2));
    expect(historisch(1)).toEqual(historisch(3));
    expect(new Set([1, 2, 3, 4, 5].map((id) => blattFarben({ id, title: "", typ: "dokument" }).join())).size).toBe(4);
  });

  it("jedes Muster wird genutzt", () => {
    const genutzt = new Set(alleGestalten({ id: 1, title: "" }).map((b) => gestaltung(b).muster));
    expect([...genutzt].sort()).toEqual(Object.keys(MUSTER).sort());
  });
});

describe("Titel bleiben im Feld", () => {
  const TITEL = [
    "Kurz",
    "Das Lied der Gezeiten",
    "Messungen an verteilten Speichern im Dauerbetrieb",
    "Grundkurs Softwaretechnik: Entwurf, Prüfung und Betrieb großer Anwendungen in Verwaltung und Industrie",
    "Donaudampfschifffahrtsgesellschaftskapitän und andere Wörter",
    "T".repeat(80),
    "日本語の非常に長いタイトルで改行がないテキストです",
    Array.from({ length: 40 }, () => "Wort").join(" "),
  ].map((t) => gekuerzt(t, 80));
  // Die Einpassungen der Muster: Ordnerrücken, Broschüre, Kreis, Berge
  const FELDER = [
    { breit: 118, hoehe: 96, max: 20, f: 0.58 },
    { breit: 150, hoehe: 40, max: 18, f: 0.58 },
    { breit: 168, hoehe: 78, max: 24, f: 0.6 },
    { breit: 168, hoehe: 300 * 0.42 - 40, max: 29, f: 0.62 },
  ];

  it("die von passe gewählte Größe mal Zeilen passt in Höhe und Breite", () => {
    for (const feld of FELDER) {
      for (const t of TITEL) {
        const { zeilen, grad } = passe(t, feld);
        expect(blockhoehe(zeilen.length, grad), `${t} in ${feld.breit}x${feld.hoehe}`).toBeLessThanOrEqual(feld.hoehe + 1e-9);
        for (const z of zeilen) expect(z.laenge * grad * feld.f).toBeLessThanOrEqual(feld.breit + 1e-9);
        expect(grad).toBeGreaterThan(5);
      }
    }
  });

  it("mit fester Zeilenlänge endet die letzte Grundlinie spätestens an der Grenze", () => {
    for (const t of TITEL) {
      const { zeilen, grad } = setze(t, 72, { n: 13, max: 30, bis: 256 });
      expect(72 + (zeilen.length - 1) * grad * 1.13).toBeLessThanOrEqual(256 + 1e-9);
      for (const z of zeilen) expect(z.laenge * grad * 0.645).toBeLessThanOrEqual(164 + 1e-9);
    }
  });

  it("auf allen Blättern bleibt jeder Text auf dem Blatt", () => {
    for (const title of TITEL) {
      for (const b of alleGestalten({ id: 2, title, author: "Bundesamt für Sicherheit in der Informationstechnik", year: 2019 })) {
        for (const t of lies(gestaltetesBlatt(b)).querySelectorAll("text")) {
          const y = Number(t.getAttribute("y"));
          const imVersatz = t.closest("g") !== null;
          if (!imVersatz) expect(y, `${gestaltung(b).muster}: ${t.textContent}`).toBeLessThanOrEqual(300);
          expect(y).toBeGreaterThan(0);
        }
      }
    }
  });

  it("die feste Zeilenlänge bleibt, solange der Platz reicht", () => {
    const { zeilen, grad } = setze("Die Reise ist auch nur ein Anfang", 38, { max: 24, bis: 106 });
    expect(zeilen.map((z) => z.text)).toEqual(["Die Reise ist", "auch nur ein", "Anfang"]);
    expect(grad).toBeCloseTo(164 / (13 * 0.645));
  });

  it("reicht die Höhe nicht, werden die Zeilen länger statt die Schrift winzig", () => {
    const t = "Ein ziemlich langer Titel für ein schmales Kopfband mit wenig Platz";
    const fest = 26 / ((Math.ceil(laenge(t) / 16) - 1) * 1.13);
    const { zeilen, grad } = setze(t, 30, { n: 16, max: 21, f: 0.6, bis: 56 });
    expect(30 + (zeilen.length - 1) * grad * 1.13).toBeLessThanOrEqual(56 + 1e-9);
    expect(Math.max(...zeilen.map((z) => z.laenge))).toBeGreaterThan(16);
    expect(grad).toBeGreaterThan(fest);
  });

  it("lange Wörter ohne Leerzeichen brechen um, die Schrift bleibt lesbar", () => {
    const { zeilen, grad } = setze("T".repeat(80), 72, { n: 13, max: 30, bis: 256 });
    expect(zeilen.length).toBeGreaterThan(3);
    for (const z of zeilen.slice(0, -1)) expect(z.text.endsWith("-")).toBe(true);
    expect(zeilen.map((z) => z.text.replace(/-$/, "")).join("")).toBe("T".repeat(80));
    expect(grad).toBeGreaterThan(14);
  });

  it("an eigenen Bindestrichen bricht ein langes Wort zuerst", () => {
    const { zeilen } = setze("Datenschutz-Grundverordnung", 72, { n: 13 });
    expect(zeilen.map((z) => z.text)).toEqual(["Datenschutz-", "Grundverordnung"]);
  });

  it("Zeichen in voller Breite zählen mehr, die Zeile wird nicht breiter als das Feld", () => {
    expect(laenge("日本")).toBe(3.5);
    expect(laenge("Müller")).toBe(6);
    expect(laenge("Müller")).toBe(6);
    const { zeilen, grad } = setze("日本語の非常に長いタイトルで改行がないテキストです", 72, { n: 13 });
    for (const z of zeilen) expect([...z.text.replace(/ /g, "")].length * grad).toBeLessThanOrEqual(164);
    expect(grad).toBeGreaterThan(9);
  });

  it("ein leerer Titel heißt Ohne Titel, sehr lange enden mit drei Punkten", () => {
    expect(texte(gestaltetesBlatt({ id: 1, title: "   " }))).toContain("Ohne Titel");
    const lang = gekuerzt(Array.from({ length: 60 }, (_, i) => `Wort${i}`).join(" "), 80);
    expect(laenge(lang)).toBeLessThanOrEqual(80);
    expect(lang.endsWith(" ...")).toBe(true);
    expect(gekuerzt("Kurz genug", 80)).toBe("Kurz genug");
  });

  it("Dokumente zeigen Autor und Jahr, was davon da ist", () => {
    expect(texte(gestaltetesBlatt({ id: 1, title: "Handbuch", author: "Firma", year: 2016, typ: "dokument" }))).toContain("Firma, 2016");
    expect(texte(gestaltetesBlatt({ id: 1, title: "Handbuch", year: 2016, typ: "dokument" }))).toContain("2016");
    expect(texte(gestaltetesBlatt({ id: 1, title: "Handbuch", typ: "dokument" }))).toEqual(["Handbuch"]);
  });
});

describe("Umschlag", () => {
  const buch = { id: 11, title: "Sommer am Leuchtturm", author: "Lena Hofer", gattung: "liebesroman", cover_path: "11.jpg", file_format: "epub" };

  it("gestaltet zeigt das Blatt, kein Bild", () => {
    const { container } = render(Umschlag, { props: { buch: { ...buch, umschlag: "gestaltet" } } });
    expect(container.querySelector(".umschlag svg")).not.toBeNull();
    expect(container.querySelector(".umschlag img")).toBeNull();
    expect(container.querySelector(".umschlag")?.textContent).toContain("Lena Hofer");
  });

  it("Titelseite zeigt das Bild vom Server", () => {
    const { container } = render(Umschlag, { props: { buch: { ...buch, umschlag: "titelseite" } } });
    expect(container.querySelector(".umschlag img")).not.toBeNull();
    expect(container.querySelector(".umschlag svg")).toBeNull();
  });

  it("reine Textdatei ohne Bild und ausbleibendes Bild zeigen das Blatt", async () => {
    const text = render(Umschlag, { props: { buch: { ...buch, cover_path: "", file_format: "txt" } } });
    expect(text.container.querySelector(".umschlag svg")).not.toBeNull();
    const bild = render(Umschlag, { props: { buch: { ...buch, id: 12 } } });
    await fireEvent.error(bild.container.querySelector("img")!);
    expect(bild.container.querySelector(".umschlag svg")).not.toBeNull();
  });
});

describe("Buchkopf", () => {
  const buch: BuchEinzeln = {
    id: 21, hash: "", title: "Das Lied der Gezeiten", author: "Mara Lindqvist", publisher: "", file_format: "epub", file_size: 414000, cover_path: "21.jpg", page_count: 31, year: 2010,
    isbn: "", typ: "", gattung: "krimi", umschlag: "gestaltet", umschlag_schlicht: true, umschlag_wahl: "", sammlung_id: null, band_nummer: "", is_favorite: false,
    is_to_read: false, rating: 0, reading_position: "", last_read_at: null, categories: [], sammlung: null, created_at: "", updated_at: "", language: "", description: "",
    file_name: "", authors: [],
  };

  beforeEach(() => {
    arten.typen = [{ id: "dokument", name: "Dokument" }];
    arten.gattungen = [{ id: "krimi", name: "Krimi" }];
  });

  it("nennt Art und Gattung bei den Angaben", () => {
    render(Buchkopf, { props: { buch, onneu: () => {}, ongeaendert: () => {} } });
    const angaben = [...document.querySelectorAll(".angaben dt")].map((dt) => `${dt.textContent}: ${dt.nextElementSibling?.textContent}`);
    expect(angaben).toContain("Art: Buch");
    expect(angaben).toContain("Gattung: Krimi");
  });

  it("die Wahl des Umschlags gibt es nur bei fast weißer Titelseite oder eigener Wahl", () => {
    render(Buchkopf, { props: { buch: { ...buch, umschlag_schlicht: false, umschlag: "titelseite" }, onneu: () => {}, ongeaendert: () => {} } });
    expect(screen.queryByRole("group", { name: "Umschlag" })).toBeNull();
  });

  it("Titelseite wählen schickt die Wahl und übernimmt, was der Server sagt", async () => {
    const anfragen: { methode: string; adresse: string; daten: unknown }[] = [];
    globalThis.fetch = vi.fn((adresse: string, init?: RequestInit) => {
      anfragen.push({ methode: init?.method ?? "GET", adresse, daten: init?.body ? JSON.parse(String(init.body)) : null });
      return Promise.resolve(new Response(JSON.stringify({ ...buch, umschlag: "titelseite", umschlag_wahl: "titelseite" })));
    }) as unknown as typeof fetch;
    const onneu = vi.fn();
    render(Buchkopf, { props: { buch, onneu, ongeaendert: () => {} } });
    const gruppe = screen.getByRole("group", { name: "Umschlag" });
    expect(gruppe.querySelector("[aria-pressed=true]")?.textContent?.trim()).toBe("Gestaltet");
    await fireEvent.click(screen.getByRole("button", { name: "Titelseite" }));
    await waitFor(() => expect(onneu).toHaveBeenCalledWith({ umschlag: "titelseite", umschlag_wahl: "titelseite", umschlag_schlicht: true }));
    expect(anfragen).toEqual([{ methode: "PATCH", adresse: "/api/books/21", daten: { umschlag_wahl: "titelseite" } }]);
  });
});
