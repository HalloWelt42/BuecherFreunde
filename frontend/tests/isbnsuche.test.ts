// BF-111 und BF-112: ISBN im Buch (Gruppen, Vorwahl, Beschriftung, Stufe nach dem Prüfen), Übernehmen ins Formular statt ins Buch,
// dieselbe Werkzeugreihe beim Bearbeiten. Bücher, Personen und Nummern sind erfunden.
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import BuchBearbeiten from "../src/ansichten/buch/BuchBearbeiten.svelte";
import { vergleiche } from "../src/ansichten/buch/angaben";
import { Buchformular } from "../src/ansichten/buch/formular.svelte";
import { anderezeile, einstufung, formenzeile, fremdHerkunft, gruppiere, kopfzeile, pruefstand, ruhemeldung, vorwahl } from "../src/ansichten/buch/isbn";
import { stellenort, stellenziel } from "../src/ansichten/buch/stelle";
import type { Einstufung, Fundort, Isbnkandidat, Isbnsuche } from "../src/lib/api/books";
import { quellen } from "../src/lib/stand/quellen.svelte";
import type { BuchEinzeln } from "../src/lib/typen";

const BUCH = { id: 7, title: "Die Möwen von Musterstadt", author: "Erika Beispiel", isbn: "", year: null, publisher: "", language: "de", page_count: 320, typ: "buch", gattung: "",
  sammlung_id: null, band_nummer: "", description: "", file_format: "pdf", cover_path: "", categories: [{ id: 1, name: "Romane" }], updated_at: "" } as unknown as BuchEinzeln;

const text = (stufe: Einstufung["stufe"], was = "Erika Beispiel, Die Möwen von Musterstadt"): Einstufung => ({ stufe, quelle: "", basis: "im Text", was, warum: "" });

function kandidat(isbn: string, fundort: Fundort, stufe: Einstufung["stufe"], ueber: Partial<Isbnkandidat> = {}): Isbnkandidat {
  return { isbn, isbn13: isbn.replace(/-/g, ""), formen: [], ausgabe: "", funde: 1, fundort, text: text(stufe), quelle: null,
    stellen: [{ seite: 4, prozent: 1.2, fundort, ausschnitt: `ISBN <mark>${isbn}</mark>`, funde: 1 }], ...ueber };
}

const DRUCK = kandidat("978-3-99999-241-9", "impressum", "passt", { ausgabe: "druck", funde: 3, formen: ["9783999992419", "9 783999 992419"] });
const EBOOK = kandidat("978-3-99999-255-6", "impressum", "passt", { ausgabe: "ebook" });
const ANZEIGE = kandidat("978-3-99999-118-4", "verlagsanzeige", "fremd", { stellen: [{ seite: 310, prozent: 96.8, fundort: "verlagsanzeige", ausschnitt: "", funde: 1 }] });
const LITERATUR = kandidat("978-3-99999-402-4", "literaturliste", "fremd", { formen: ["3-99999-402-9"] });
const SUCHE: Isbnsuche = { kandidaten: [DRUCK, EBOOK, ANZEIGE, LITERATUR], funde: 6, aktuell: "", seiten: 320 };

describe("ISBN im Buch", () => {
  it("stellt fremde Bücher unter Andere Bücher und wählt die beste eigene vor", () => {
    expect(gruppiere(SUCHE.kandidaten)).toEqual({ eigen: [DRUCK, EBOOK], andere: [ANZEIGE, LITERATUR] });
    expect(vorwahl(SUCHE.kandidaten)).toBe(DRUCK.isbn);
    expect(vorwahl([ANZEIGE, LITERATUR])).toBe("");          // nur fremde: nichts vorgewählt
    expect(kopfzeile(SUCHE)).toBe("4 ISBN in 6 Funden. Zuerst, was zu Titel und Autor passt.");
    expect(anderezeile([ANZEIGE, LITERATUR])).toBe("2, aus Verlagsanzeige und Literaturliste");
    expect(anderezeile([LITERATUR])).toBe("1, aus der Literaturliste");
    expect(formenzeile(DRUCK)).toBe("auch 9783999992419 und 9 783999 992419");
    expect(formenzeile(LITERATUR)).toBe("auch als ISBN-10 3-99999-402-9");
  });

  it("zeigt nach dem Prüfen die Quelle, ohne Fund die Quellen, und erneut, wenn eine ruht", () => {
    const quelle: Einstufung = { stufe: "aehnlich", quelle: "google_books", basis: "Verzeichnis 1", was: "<mark>Möwen von Musterstadt</mark>", warum: "Titel ohne Artikel" };
    expect(einstufung({ kandidat: EBOOK, pruefung: null, prueft: false })).toBe(EBOOK.text);
    expect(einstufung({ kandidat: EBOOK, pruefung: { isbn: EBOOK.isbn, einstufung: quelle, hinweise: [], ruht: false }, prueft: false })).toBe(quelle);
    const ruht = { kandidat: EBOOK, pruefung: { isbn: EBOOK.isbn, einstufung: null, hinweise: ["Verzeichnis 1 macht Pause bis 14:30: zu viele Anfragen"], ruht: true }, prueft: false };
    expect(einstufung(ruht)).toMatchObject({ stufe: "passt", basis: "Quellen", was: "keine kennt diese ISBN" });
    expect(pruefstand(ruht)).toBe("erneut");
    expect(ruhemeldung(ruht.pruefung)).toBe("Verzeichnis 1 macht Pause bis 14:30: zu viele Anfragen. Keine Quelle antwortet gerade, später noch einmal prüfen.");
    expect(pruefstand({ kandidat: EBOOK, pruefung: null, prueft: false })).toBe("offen");
    expect(pruefstand({ kandidat: { ...EBOOK, quelle }, pruefung: null, prueft: false })).toBe("fertig");     // der Lauf hat schon gefragt
  });

  it("nennt Fundort und Stelle wie die Suche im Buch", () => {
    expect(fremdHerkunft(ANZEIGE, BUCH)).toBe(" Die ISBN stammt aus der Verlagsanzeige, Seite 310.");
    expect(fremdHerkunft(ANZEIGE, { id: 7, file_format: "epub" })).toBe(" Die ISBN stammt aus der Verlagsanzeige, bei 96,8 %.");
    expect(fremdHerkunft(null, BUCH)).toBe("");
    expect(stellenziel(BUCH, { seite: 4, prozent: 1.2 }, "978")).toBe("/book/7/read?page=4&q=978");
    expect(stellenort({ id: 7, file_format: "epub" }, { seite: 4, prozent: 1.2 })).toBe("1,2 %");
  });

  it("nimmt eine 0 bei Jahr oder Seiten nicht als Angabe", () => {
    expect(vergleiche({ titel: "Die Möwen von Musterstadt", seiten: 0, jahr: 0 }, { titel: "Die Möwen von Musterstadt", seiten: 320 }, "").map((z) => [z.schluessel, z.gleich])).toEqual([["titel", true], ["seiten", true]]);
  });
});

describe("Übernehmen beim Bearbeiten", () => {
  it("setzt die gewählten Felder, den Umschlag und die Regale ins Formular", async () => {
    quellen.liste = [{ kennung: "dnb", name: "Verzeichnis 3" } as never];
    const f = new Buchformular(BUCH);
    const vorschlag = { titel: "Die Möwen von Musterstadt", verlag: "Beispielverlag", jahr: 2019, isbn: "978-3-99999-241-9", cover_url: "https://bild.example/m.jpg", kategorien: ["Küste"] };
    await f.angaben({ vorschlag, quelle: "dnb", gewaehlt: new Set(["verlag", "jahr", "isbn", "cover", "kategorien"]), listen: new Set() });
    expect(f.eingabe).toMatchObject({ publisher: "Beispielverlag", year: "2019", isbn: "978-3-99999-241-9", title: "Die Möwen von Musterstadt" });
    expect(f.eingesetzt).toEqual(["publisher", "year", "isbn"]);
    expect(f.umschlag).toEqual({ adresse: "https://bild.example/m.jpg", ausDatei: false, quelle: "dnb" });
    expect(f.regaleAngaben).toEqual(["Küste"]);
    expect(f.hinweis).toBe("4 Felder aus Verzeichnis 3 eingesetzt, dazu das Regal Küste. Gespeichert wird mit Speichern.");
    expect(f.aktuell()).toMatchObject({ verlag: "Beispielverlag", hat_cover: true, kategorien: ["Romane", "Küste"] });
    expect(f.aenderungen()).toEqual({ isbn: "978-3-99999-241-9", publisher: "Beispielverlag", year: 2019 });
  });

  it("speichert erst mit Speichern, alles in einem Zug", async () => {
    const anfragen: [string, string, unknown][] = [];
    globalThis.fetch = vi.fn((weg: string, o: RequestInit = {}) => {
      anfragen.push([o.method ?? "GET", weg, o.body ? JSON.parse(String(o.body)) : null]);
      return Promise.resolve(new Response(JSON.stringify(weg.includes("uebernehmen") ? { uebernommen: true, felder: [], kategorien_erstellt: 1, cover_gespeichert: true, hinweis: "" } : {}), { status: 200 }));
    }) as unknown as typeof fetch;
    const f = new Buchformular(BUCH);
    await f.isbn("978-3-99999-241-9");
    await f.regale(["Küste"]);
    expect(anfragen).toEqual([]);
    expect(await f.speichern()).toBe("");
    expect(anfragen).toEqual([["PATCH", "/api/books/7", { isbn: "978-3-99999-241-9" }], ["POST", "/api/ai/buch/7/kategorien-uebernehmen", { kategorien: ["Küste"] }]]);
  });
});

describe("Bearbeiten mit den Werkzeugen", () => {
  // jsdom kennt showModal nicht; das Fenster der App öffnet sich damit
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
      this.removeAttribute("open");
    };
  });

  function server(wege: Record<string, unknown>) {
    const f = vi.fn((weg: string, o: RequestInit = {}) => {
      const antwort = wege[`${o.method ?? "GET"} ${weg.split("?")[0]}`];
      return Promise.resolve(new Response(JSON.stringify(antwort ?? []), { status: 200 }));
    });
    globalThis.fetch = f as unknown as typeof fetch;
    return f;
  }

  it("findet die ISBN im Buch, je ISBN eine Zeile, und setzt sie nur ins Feld", async () => {
    const f = server({ "POST /api/books/7/isbn-scan": SUCHE, "GET /api/metadata/quellen": [{ kennung: "dnb", name: "Verzeichnis 3", art: "buch", bereit: true, aktiv: true }] });
    render(BuchBearbeiten, { buch: BUCH, onabbruch: () => {}, onfertig: () => {} });
    const reihe = screen.getByRole("group", { name: "Angaben holen" });
    expect(within(reihe).getAllByRole("button").map((b) => b.textContent?.trim())).toEqual(["Angaben suchenSuchen", "Lexikon", "Buchtext", "Datei", "Umschlag"]);
    await fireEvent.click(screen.getByRole("button", { name: "Im Buch suchen" }));
    const fenster = await screen.findByRole("dialog", { name: "ISBN im Buch" });
    const wahl = within(fenster).getAllByRole("radio");
    expect(wahl.map((r) => r.getAttribute("aria-label"))).toEqual([`${DRUCK.isbn} wählen`, `${EBOOK.isbn} wählen`, `${ANZEIGE.isbn} wählen`, `${LITERATUR.isbn} wählen`]);
    expect((wahl[0] as HTMLInputElement).checked).toBe(true);
    expect(within(fenster).getByText("Andere Bücher")).toBeTruthy();
    expect(within(fenster).getByText("auch 9783999992419 und 9 783999 992419")).toBeTruthy();
    await fireEvent.click(within(fenster).getByRole("button", { name: "ISBN übernehmen" }));
    const feld = screen.getByLabelText("ISBN") as HTMLInputElement;
    expect(feld.value).toBe(DRUCK.isbn);
    expect(feld.closest(".feld")?.classList.contains("eingesetzt")).toBe(true);
    expect(screen.getByText("ISBN aus dem Buch eingesetzt. Gespeichert wird mit Speichern.")).toBeTruthy();
    expect(f.mock.calls.some(([, o]) => (o as RequestInit | undefined)?.method === "PATCH")).toBe(false);
  });

  it("sagt, wenn im Buch keine ISBN steht, und bietet den Weg über Titel und Autor", async () => {
    server({ "POST /api/books/7/isbn-scan": { kandidaten: [], funde: 0, aktuell: "", seiten: 320 } });
    render(BuchBearbeiten, { buch: BUCH, onabbruch: () => {}, onfertig: () => {} });
    await fireEvent.click(screen.getByRole("button", { name: "Im Buch suchen" }));
    expect(await screen.findByText("Im Buch steht keine ISBN.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Über Titel und Autor suchen" })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
