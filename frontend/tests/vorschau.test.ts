// BF-80: Hochladen mit Vorschau. Was die Vorschau aus der Antwort des Servers zeigt, die Zeile "Zum Bestätigen", der Weg einer
// Datei in eine Vorschau oder zu einem Buch, die Folgen des Verwerfens. Alle Namen sind erfunden.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { annahmeDienst } from "../src/lib/api/annahme";
import { Hochlader } from "../src/lib/annahme/hochlader";
import type { AnnahmeDienst, AnnahmeEintrag, NeueDatei, Vorschaukurz } from "../src/lib/annahme/typen";
import {
  ablagetext, artAnzeige, dateizeichen, doppelFuerAlle, doppelwerte, filterzahlen, fusstext, kopfzeile, nichtUebernommen, passt, verwerfliste,
  verwerfsaetze, vonHand, zusatz,
} from "../src/lib/annahme/vorschau";
import type { Doppel, Verwerffolgen, Vorschauzeile, Zuordnung } from "../src/lib/annahme/vorschautypen";
import { fuegeZusammen, vorschauzeile } from "../src/lib/annahme/zeilen";
import { seitWann } from "../src/lib/format";
import { rueckfrage } from "../src/lib/stand/rueckfrage.svelte";
import Rueckfrage from "../src/lib/teile/Rueckfrage.svelte";

const wert = <T,>(w: T, herkunft: Zuordnung["art"]["herkunft"] = "regel") => ({ wert: w, herkunft, grund: "" });

function zuordnung(ueber: Partial<Zuordnung> = {}): Zuordnung {
  return {
    art: wert("buch"), gattung: null, kategorien: wert<number[]>([]), etiketten: wert<string[]>([]), sammlung: wert<number | null>(null), band: wert(""),
    sprache: wert("de", "datei"), doppel: { art: "neu", wahl: "neu", herkunft: null, grund: "" }, ziel: null, nicht: "", hinweise: [], bestaetigt: false,
    von_profil: null, ...ueber,
  };
}

function zeile(id: number, ueber: Partial<Vorschauzeile> = {}): Vorschauzeile {
  return { id, name: `Probe ${id}.epub`, groesse: 1000, ordner: "", stand: "bestaetigen", text: "", rolle: "buch", buch_id: null, umschlag: false, ki: "", material: 0, gelesen: null, felder: zuordnung(), ablage: null, ...ueber };
}

const doppel = (art: Doppel["art"], wahl: Doppel["wahl"]): Doppel => ({ art, wahl, herkunft: "bestand", grund: "" });

function kurz(ueber: Partial<Vorschaukurz> = {}): Vorschaukurz {
  return { id: "v-1", name: "Werkbank.zip", quelle: "hochladen", stand: "offen", dateien: 14, warten: 13, laeuft: 0, ki: 0, groesse: 41_800_000, hinweis: "", angelegt_am: "2026-11-26T13:12:00Z", geaendert_am: "", ...ueber };
}

function eintrag(ueber: Partial<AnnahmeEintrag>): AnnahmeEintrag {
  return { id: 1, name: "Probe.pdf", groesse: 1000, sha256: "", empfangen: 1000, teil_groesse: 4, stand: "bestaetigen", schritt: 4, anteil: 0, text: "", buch_id: null, quelle: "hochladen", angelegt_am: "", geaendert_am: "", ...ueber };
}

describe("Was die Vorschau zeigt", () => {
  const zeilen = [
    zeile(1),
    zeile(2, { felder: zuordnung({ art: wert("anleitung") }) }),
    zeile(3, { rolle: "material", felder: zuordnung({ art: wert("material", "datei"), ziel: { buch_id: null, aufnahme: 1, titel: "Probe 1" } }) }),
    zeile(4, { rolle: "doppel", felder: zuordnung({ doppel: doppel("gleich", "weglassen") }) }),
    zeile(5, { felder: zuordnung({ doppel: doppel("format", "format") }) }),
    zeile(6, { rolle: "rest", name: "Karte.png", felder: zuordnung({ art: wert(""), nicht: "Bild ohne Buch gleichen Namens" }) }),
    zeile(7, { rolle: "zip", name: "Werkbank.zip", felder: null }),
  ];

  it("zählt je Filter nur die Liste oben: Werke, Material und Doppel, ohne ZIP und Rest", () => {
    expect(filterzahlen(zeilen)).toEqual({ alle: 5, buecher: 3, besonderes: 1, material: 1, doppel: 2 });
    expect(zeilen.filter((z) => passt(z, "besonderes")).map((z) => z.id)).toEqual([2]);
    expect(zeilen.filter(nichtUebernommen).map((z) => z.id)).toEqual([6]);
  });

  it("nennt im Fuß nur, was es gibt, und im Kopf die Zahl nur einmal", () => {
    expect(fusstext({ gesamt: 14, uebernehmen: 11, buecher: 7, besonderes: 3, material: 2, formate: 1, weglassen: 1, nicht: 2, offen: 0, laeuft: 0, ki: 1 })).toBe("11 übernehmen, 1 weglassen, 2 nicht übernommen");
    expect(fusstext({ gesamt: 1, uebernehmen: 1, buecher: 1, besonderes: 0, material: 0, formate: 0, weglassen: 0, nicht: 0, offen: 0, laeuft: 0, ki: 0 })).toBe("1 übernehmen");
    expect(kopfzeile(kurz())).toBe("Werkbank.zip, 14 Dateien, 41,8 MB");
    expect(kopfzeile(kurz({ name: "3 Dateien", dateien: 3, groesse: 2000 }))).toBe("3 Dateien, 2 KB");
  });

  it("bietet beim Doppel nur an, was geht: dieselbe Datei nur weglassen, ein Format auch als eigenes Buch", () => {
    expect(doppelwerte(doppel("gleich", "weglassen")).map(([w]) => w)).toEqual(["weglassen"]);
    expect(doppelwerte(doppel("format", "format")).map(([w]) => w)).toEqual(["format", "eigenes"]);
    expect(doppelwerte(doppel("format", "weglassen")).map(([w]) => w)).toEqual(["format", "eigenes", "weglassen"]);
    expect(doppelwerte(doppel("neu", "weglassen")).map(([w]) => w)).toEqual(["neu", "weglassen"]);
    const alle = doppelFuerAlle([zeilen[0], zeilen[3]]);
    expect(alle).toMatchObject({ weglassen: true, eigenes: false, format: false });
    expect(doppelFuerAlle([zeilen[4]])).toMatchObject({ format: true, eigenes: true });
  });

  it("zeigt Art und Unterart mit den Namen des Servers", () => {
    const name = (id: string) => ({ anleitung: "Anleitung" })[id] ?? id;
    expect(artAnzeige("anleitung", name)).toEqual({ symbol: "shapes", text: "Besonderes", klein: "Anleitung" });
    expect(artAnzeige("buch", name).text).toBe("Buch");
    expect(artAnzeige("", name).text).toBe("Offen");
  });

  it("liest den Zusatz des Materials aus dem Namen und das Zeichen aus der Endung", () => {
    expect(zusatz("Holm - Messen mit Licht - Schaltpläne.pdf", "Holm - Messen mit Licht.pdf")).toBe("Schaltpläne");
    expect(zusatz("Messen (Lösungen).zip", "Messen.pdf")).toBe("Lösungen");
    expect(zusatz("Anderes.pdf", "Messen.pdf")).toBe("");
    expect(dateizeichen("Karte.PNG")).toBe("file-image");
    expect(dateizeichen("liste.xlsx")).toBe("table-cells");
    expect(dateizeichen("unbekannt.xyz")).toBe("file");
  });

  it("sagt, wohin eine Datei kommt", () => {
    expect(ablagetext({ ort: "kellerwolke", ordner: "Apps/BücherFreunde/Bücher/P", name: "Probe.epub" })).toBe("Kellerwolke, Apps/BücherFreunde/Bücher/P/Probe.epub");
    expect(ablagetext({ ort: "bleibt", ordner: "/eingang/7", name: "" })).toBe("Bleibt liegen, /eingang/7");
  });
});

describe("Folgen des Verwerfens", () => {
  const folgen = (ueber: Partial<Verwerffolgen>): Verwerffolgen => ({
    vorschau: "v-1", name: "Werkbank.zip", stand: "s1", papierkorb: 0, endgueltig: 0, bleibt: 0,
    dateien: [
      { id: 1, name: "Werkbank.zip", ordner: "", groesse: 10, wirkung: "papierkorb", pfad: "Apps/BücherFreunde/Eingang/Werkbank.zip" },
      { id: 2, name: "Probe 1.epub", ordner: "Romane", groesse: 10, wirkung: "papierkorb", pfad: "Apps/BücherFreunde/Eingang/7 Werkbank/Romane/Probe 1.epub" },
      { id: 3, name: "Doppel.pdf", ordner: "", groesse: 10, wirkung: "nichts", pfad: "" },
    ],
    ...ueber,
  });

  it("nennt Papierkorb, endgültig und was bleibt, dazu verlorene Änderungen nur, wenn es welche gibt", () => {
    expect(verwerfsaetze(folgen({ papierkorb: 2 }), false)).toEqual([
      "Alle 2 Dateien kommen in den Papierkorb der Kellerwolke und lassen sich dort zurückholen.",
      "Ins Regal kommt nichts, im Bestand ändert sich nichts.",
    ]);
    const ohneWolke = verwerfsaetze(folgen({ endgueltig: 1, bleibt: 1 }), true);
    expect(ohneWolke[0]).toBe("1 Datei wird auf diesem Gerät endgültig gelöscht und lässt sich nicht zurückholen.");
    expect(ohneWolke[1]).toBe("1 Datei bleibt im Ordner, wo sie liegt.");
    expect(ohneWolke.at(-1)).toBe("Deine Änderungen an der Zuordnung gehen verloren.");
  });

  it("listet jede Datei mit ihrem Ordner unter dem gemeinsamen Ort, ohne die, die es nicht gibt", () => {
    expect(verwerfliste(folgen({}))).toEqual({ titel: "Apps/BücherFreunde/Eingang", eintraege: ["Werkbank.zip", "Romane/Probe 1.epub"] });
  });

  it("weiß, ob jemand schon von Hand zugeordnet hat", () => {
    expect(vonHand({ zeilen: [zeile(1)] })).toBe(false);
    expect(vonHand({ zeilen: [zeile(1, { felder: zuordnung({ sprache: wert("en", "nutzer") }) })] })).toBe(true);
  });

  it("zeigt in der Rückfrage jede Datei unter ihrem Ort", async () => {
    render(Rueckfrage);
    const antwort = rueckfrage.stelle({ titel: "Vorschau verwerfen?", folgen: ["Ins Regal kommt nichts."], liste: verwerfliste(folgen({})), ja: "Verwerfen" });
    expect(await screen.findByText("Apps/BücherFreunde/Eingang")).toBeTruthy();
    expect(screen.getByText("Romane/Probe 1.epub")).toBeTruthy();
    await fireEvent.click(screen.getByText("Abbrechen"));
    expect(await antwort).toBe(false);
  });
});

describe("Zum Bestätigen", () => {
  it("steht als eine Zeile je Vorschau, wartet an der Station Regal und führt zur Vorschau", () => {
    const z = vorschauzeile(kurz({ laeuft: 2 }), new Date("2026-11-26T18:00:00Z"));
    expect(z).toMatchObject({ gruppe: "bestaetigen", wort: "Zum Bestätigen", vorschau: "v-1", handlungen: ["ansehen"], groesse: "41,8 MB" });
    expect(z.stationen).toEqual(["fertig", "fertig", "fertig", "fertig", "wartet", "offen"]);
    expect(z.text).toMatch(/^14 Dateien, 2 laufen noch, seit heute \d\d:\d\d$/);
  });

  it("faltet Wartendes einer offenen Vorschau in ihre Zeile, was noch läuft, steht für sich", () => {
    const eintraege = [eintrag({ id: 1, vorschau: "v-1" }), eintrag({ id: 2, vorschau: "v-1", stand: "liest", schritt: 2 }), eintrag({ id: 3, vorschau: "v-alt", stand: "fertig" })];
    const zeilen = fuegeZusammen(eintraege, [], [kurz()]);
    expect(zeilen.map((z) => z.schluessel)).toEqual(["vorschau-v-1", "eintrag-2", "eintrag-3"]);
  });

  it("sagt, seit wann etwas wartet", () => {
    const jetzt = new Date(2026, 10, 26, 18, 0);
    expect(seitWann(new Date(2026, 10, 26, 14, 12).toISOString(), jetzt)).toBe("seit heute 14:12");
    expect(seitWann(new Date(2026, 10, 25, 9, 5).toISOString(), jetzt)).toBe("seit gestern 09:05");
    expect(seitWann(new Date(2026, 10, 24, 9, 5).toISOString(), jetzt)).toBe("seit Dienstag, 24.11.");
    expect(seitWann(new Date(2026, 9, 1, 9, 5).toISOString(), jetzt)).toBe("seit 01.10.2026");
  });
});

describe("Weg einer Datei aus dem Browser", () => {
  it("der Hochlader gibt jeder Datei ihr Ziel mit", async () => {
    const angelegt: NeueDatei[] = [];
    const dienst: AnnahmeDienst = {
      anlegen: async (d) => (angelegt.push(d), eintrag({ id: angelegt.length, stand: "liest", empfangen: d.groesse, groesse: d.groesse })),
      stand: async () => eintrag({}),
      teil: async () => eintrag({}),
    };
    const h = new Hochlader(dienst, async () => "ab".repeat(32), { warte: async () => {} });
    h.fuegeHinzu([new File(["a"], "Probe.epub")], { art: "vorschau", vorschau: "v-9", anreichern: true });
    h.fuegeHinzu([new File(["bb"], "Lösungen.zip")], { art: "material", buch: 12, entpacken: true });
    await vi.waitFor(() => expect(angelegt).toHaveLength(2));
    expect(angelegt[0].ziel).toEqual({ art: "vorschau", vorschau: "v-9", anreichern: true });
    expect(angelegt[1].ziel).toEqual({ art: "material", buch: 12, entpacken: true });
  });

  it("meldet sie an der Annahme mit der Vorschau oder am Buch als Material an", async () => {
    const f = vi.fn((_weg: string, _o: RequestInit) => Promise.resolve(new Response(JSON.stringify(eintrag({})), { status: 200 })));
    globalThis.fetch = f as unknown as typeof fetch;
    await annahmeDienst.anlegen({ name: "Probe.epub", groesse: 1, sha256: "", ziel: { art: "vorschau", vorschau: "v-9", anreichern: false } });
    await annahmeDienst.anlegen({ name: "Lösungen.zip", groesse: 2, sha256: "", ziel: { art: "material", buch: 12, entpacken: true } });
    await annahmeDienst.anlegen({ name: "Einzeln.pdf", groesse: 3, sha256: "", ziel: { art: "vorschau", vorschau: null, anreichern: true } });
    const [eins, zwei, drei] = f.mock.calls.map(([weg, o]) => [weg, JSON.parse(String(o.body))]);
    expect(eins).toEqual(["/api/annahme", { name: "Probe.epub", groesse: 1, sha256: "", anreichern: false, vorschau: "v-9" }]);
    expect(zwei).toEqual(["/api/books/12/material", { name: "Lösungen.zip", groesse: 2, sha256: "", entpacken: true }]);
    expect(drei[1]).not.toHaveProperty("vorschau");
  });
});
