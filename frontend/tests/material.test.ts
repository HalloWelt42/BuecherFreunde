// BF-81 und BF-80: Begleitmaterial je Buch, Lesen in der App, weitere Formate, Treffer im Material, Folgen beim Löschen.
// Alle Namen sind erfunden.
import { render, screen } from "@testing-library/svelte";
import Begleitmaterial from "../src/ansichten/buch/Begleitmaterial.svelte";
import { formatAdresse, gemerktesFormat, merkeFormat } from "../src/ansichten/buch/leseformat";
import { folgensaetze } from "../src/ansichten/buch/loeschen";
import { materialfolgensaetze, namensteile } from "../src/ansichten/buch/material.svelte";
import { mitMaterial, type Fund } from "../src/ansichten/suche/suchlauf.svelte";
import type { Faehigkeit, Ich } from "../src/lib/api/familie";
import type { Material } from "../src/lib/api/material";
import { formatfassung, ladeLesefassung, materialfassung } from "../src/lib/leser/lesefassung";
import { ich } from "../src/lib/stand/ich.svelte";
import type { BuchEinzeln, Materialtreffer, Treffer } from "../src/lib/typen";

const BUCH = { id: 12, title: "Messen mit Licht", author: "Ida Holm", file_format: "pdf", file_name: "Messen mit Licht.pdf", reading_position: "", page_count: 40,
  dateien: [{ id: "d1", format: "pdf", name: "Messen mit Licht.pdf", groesse: 10, haupt: true }, { id: "d2", format: "epub", name: "Messen mit Licht.epub", groesse: 8, haupt: false }] } as unknown as BuchEinzeln;

function material(ueber: Partial<Material> = {}): Material {
  return { id: "m-1", buch_id: 12, name: "Schaltpläne.pdf", art: "pdf", art_name: "PDF", zeichen: "file-pdf", groesse: 900_000, ort: "geraet", pfad: "/speicher/ab/Material/Schaltpläne.pdf", herkunft: "buchseite", oeffnen: true, lesbar: true, text_stand: "fertig", text_seiten: 12, angelegt_am: "", ...ueber };
}

const darf = (...faehigkeiten: Faehigkeit[]) => ich.setze({ profil: { id: "p-1", name: "Malve", rolle: faehigkeiten.includes("bearbeiten") ? "erwachsen" : "kind" }, faehigkeiten } as unknown as Ich);

function server(wege: Record<string, unknown>) {
  const f = vi.fn((weg: string) => Promise.resolve(new Response(JSON.stringify(wege[weg.split("?")[0]] ?? {}), { status: 200 })));
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

afterEach(() => ich.setze(null));

describe("Begleitmaterial in der App lesen", () => {
  it("öffnet PDF, EPUB, Text, Markdown und Bilder als eigene Fassung ohne Stellen, mit Lesestand auf dem Gerät", () => {
    const f = materialfassung(BUCH, material());
    expect(f).toMatchObject({ format: "pdf", datei: "/api/books/12/material/m-1/datei", anhang: "/api/books/12/material/m-1/datei?herunterladen=true", mitStellen: false, mitBuchtext: false, titel: "Schaltpläne.pdf, zu Messen mit Licht" });
    expect(f?.ort.pfad).toBe("/book/12/material/m-1");
    expect(materialfassung(BUCH, material({ art: "markdown", name: "Korrekturen.md" }))?.format).toBe("md");
    expect(materialfassung(BUCH, material({ art: "bild", name: "Rückseite.jpg" }))?.format).toBe("bild");
    expect(materialfassung(BUCH, material({ art: "zip", oeffnen: false }))).toBeNull();
  });

  it("merkt den Lesestand des Materials nur auf diesem Gerät", async () => {
    const f = materialfassung(BUCH, material())!;
    await f.ort.sende('pdf:{"page":3}');
    expect(materialfassung(BUCH, material())!.position).toBe('pdf:{"page":3}');
  });

  it("findet Material und Formate zur Adresse des Lesers", async () => {
    server({ "/api/books/12/material": { material: [material()], funde: [], ort: "geraet", groesse: 1 } });
    expect(await ladeLesefassung(BUCH, undefined, { material: "m-1" })).toMatchObject({ format: "pdf", mitStellen: false });
    await expect(ladeLesefassung(BUCH, undefined, { material: "fehlt" })).rejects.toThrow("Dieses Begleitmaterial gibt es nicht");
    expect(await ladeLesefassung(BUCH, undefined, { format: "epub" })).toMatchObject({ format: "epub", datei: "/api/books/12/file?format=epub", mitBuchtext: false });
    expect(await ladeLesefassung(BUCH, undefined, { format: "pdf" })).toMatchObject({ mitStellen: true, mitBuchtext: true });
    await expect(ladeLesefassung(BUCH, undefined, { format: "mobi" })).rejects.toThrow("Dieses Buch gibt es nicht als MOBI");
  });
});

describe("Format zum Lesen (BF-80)", () => {
  it("liest ein weiteres Format unter eigener Adresse und merkt die Wahl je Buch", () => {
    expect(formatfassung(BUCH, BUCH.dateien![1]).ort.pfad).toBe("/book/12/read/format/epub");
    expect(formatAdresse(12, "epub", { restart: 1 })).toBe("/book/12/read/format/epub?restart=1");
    expect(gemerktesFormat(12, BUCH.dateien!)).toBe("");
    merkeFormat(12, "epub", BUCH.dateien!);
    expect(gemerktesFormat(12, BUCH.dateien!)).toBe("epub");
    merkeFormat(12, "", BUCH.dateien!);
    expect(gemerktesFormat(12, BUCH.dateien!)).toBe("");
  });
});

describe("Begleitmaterial auf der Buchseite", () => {
  it("nennt beim Entfernen Ort, Größe, was die Suche verliert und dass das Buch bleibt", () => {
    const f = { id: "m-1", name: "Schaltpläne.pdf", buch_id: 12, titel: "Messen mit Licht", ort: "kellerwolke" as const, pfad: "Apps/BücherFreunde/Bücher/M/Messen mit Licht.material.schaltplaene.pdf", groesse: 900_000, papierkorb: true, suche: true, seiten: 12, stand: "s" };
    expect(materialfolgensaetze(f)).toEqual([
      "Die Datei kommt in den Papierkorb der Kellerwolke und lässt sich dort zurückholen: Apps/BücherFreunde/Bücher/M/Messen mit Licht.material.schaltplaene.pdf, 900 KB.",
      "Die Suche findet ihren Text nicht mehr (12 Seiten).",
      "Das Buch und das übrige Material bleiben.",
    ]);
    expect(materialfolgensaetze({ ...f, papierkorb: false, suche: false })[0]).toMatch(/^Die Datei liegt nur auf diesem Gerät und ist danach endgültig fort/);
    expect(namensteile("Korrekturen.md")).toEqual({ stamm: "Korrekturen", endung: ".md" });
    expect(namensteile("Liesmich")).toEqual({ stamm: "Liesmich", endung: "" });
  });

  it("Erwachsene ändern, ein Kind liest das Material nur", async () => {
    server({ "/api/books/12/material": { material: [material(), material({ id: "m-2", name: "Messwerte.csv", art: "tabelle", art_name: "Tabelle", oeffnen: false })], funde: [{ knoten: "k9", buch_id: 12, name: "Messen mit Licht - Lösungen.pdf", groesse: 1200, pfad: "", gefunden_am: "" }], ort: "kellerwolke", groesse: 2 } });
    darf("lesen", "bearbeiten", "hinzufuegen", "loeschen");
    const erwachsen = render(Begleitmaterial, { buch: BUCH });
    expect(await screen.findByText("Schaltpläne.pdf")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Hinzufügen" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /umbenennen/ })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /entfernen/ })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Ja" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Öffnen" }).getAttribute("href")).toBe("/book/12/material/m-1");
    expect(screen.getByRole("link", { name: "Herunterladen" }).getAttribute("href")).toBe("/api/books/12/material/m-2/datei?herunterladen=true");
    expect(screen.getByText(/in der Kellerwolke neben dem Original/)).toBeTruthy();
    erwachsen.unmount();

    darf("lesen");
    render(Begleitmaterial, { buch: BUCH });
    expect(await screen.findByText("Schaltpläne.pdf")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Hinzufügen" })).toBeNull();
    expect(screen.queryByRole("button", { name: /umbenennen|entfernen/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Ja" })).toBeNull();
    expect(screen.getByRole("link", { name: "Öffnen" })).toBeTruthy();
  });

  it("nennt beim Löschen eines Buchs seine weiteren Formate und sein Material", () => {
    const leer = { titel: "Messen mit Licht", autor: "", notizen: 0, markierungen: 0, etiketten: 0, lesestand: false, vorlesestelle: false, regale: 0, datei: null, abschnitte: null };
    const saetze = folgensaetze({ ...leer, formate: [{ pfad: "Apps/BücherFreunde/Bücher/M/Messen mit Licht.epub", groesse: 8000, papierkorb: true }], material: [{ pfad: "Schaltpläne.pdf", groesse: 900_000, papierkorb: false }, { pfad: "Messwerte.csv", groesse: 2000, papierkorb: false }] });
    expect(saetze).toEqual([
      "1 weiteres Format kommt mit in den Papierkorb der Kellerwolke: Apps/BücherFreunde/Bücher/M/Messen mit Licht.epub, 8 KB.",
      "2 Dateien Begleitmaterial auf diesem Gerät sind danach fort: Schaltpläne.pdf, 900 KB; Messwerte.csv, 2 KB.",
    ]);
  });
});

describe("Treffer im Material (BF-81)", () => {
  const wort = (book_id: number): Fund => ({ art: "wort", schluessel: `w${book_id}`, wort: { book_id, titel: "", autor: "", snippet: "", relevanz: 1, deckblatt: null } as Treffer });
  const im = (buch_id: number, material_id: string): Materialtreffer => ({ material_id, buch_id, titel: "", autor: "", name: "", seite: 3, auszug: "", deckblatt: null });

  it("stehen gleich hinter dem Buch, zu dem sie gehören, die übrigen danach", () => {
    const funde = mitMaterial([wort(1), wort(2)], [im(1, "a"), im(9, "b"), im(1, "c")]);
    expect(funde.map((f) => f.schluessel)).toEqual(["w1", "ma-3", "mc-3", "w2", "mb-3"]);
  });
});
