// Bücher übersetzen (BF-71): Flaggenlabels, Rückfrage, Auftrag, Prüfbericht, Begriffe, Lesen der Übersetzung. Nur erfundene
// Titel und Texte.
import { fireEvent, render, screen } from "@testing-library/svelte";
import Fassungslabels from "../src/ansichten/buch/Fassungslabels.svelte";
import Buchkopf from "../src/ansichten/buch/Buchkopf.svelte";
import Uebersetzungsfrage from "../src/ansichten/buch/Uebersetzungsfrage.svelte";
import { Buchfassungen, fassungsAdresse, uebersetzbar } from "../src/ansichten/buch/fassungen.svelte";
import Offenestelle from "../src/ansichten/uebersetzung/Offenestelle.svelte";
import { ladeLesefassung, originalfassung, uebersetzungsfassung } from "../src/lib/leser/lesefassung";
import { Positionsspeicher } from "../src/lib/leser/position";
import { Lesesitzung } from "../src/lib/leser/sitzung.svelte";
import { anschluesse } from "../src/lib/stand/anschluesse.svelte";
import { auftraege } from "../src/lib/stand/auftraege.svelte";
import { buecher } from "../src/lib/stand/buecher.svelte";
import { uebersetzungen } from "../src/lib/stand/uebersetzungen.svelte";
import type { BuchEinzeln } from "../src/lib/typen";
import { klartext, stuecke } from "../src/lib/uebersetzung/marken";
import {
  auftragstext, befundname, ergebnistext, kapiteldauer, kapitelzeilen, labeltext, laufanteil, laufort, stationstext,
} from "../src/lib/uebersetzung/texte";
import type { Fassungseintrag, Kapitelstand, Laufeintrag, Laufstand, OffeneStelle } from "../src/lib/uebersetzung/typen";
import { dauer, etwa, gegen, ungefaehr, zeitKurz } from "../src/lib/uebersetzung/zeiten";

const BUCH = {
  id: 7, title: "Building Tiny Robots at Home", author: "Rita Example", authors: [{ id: 1, name: "Rita Example" }], language: "en",
  file_format: "epub", file_name: "Roboter.epub", page_count: 64, reading_position: 'epub:{"percent":25}', description: "", year: 2026,
  categories: [], sammlung: null, umschlag: "gestaltet", umschlag_wahl: "", umschlag_schlicht: false, typ: "", gattung: "",
} as unknown as BuchEinzeln;

const original = (mehr: Partial<Fassungseintrag> = {}): Fassungseintrag => ({
  id: null, sprache: "en", original: true, stand: "fertig", kapitel_fertig: null, kapitel_gesamt: null, fertig_gegen: null, modell: "",
  pruefmodell: "", angelegt: "2026-11-26T10:00:00Z", geaendert: "2026-11-26T10:00:00Z", gewaehlt: true, ...mehr,
});
const deutsch = (mehr: Partial<Fassungseintrag> = {}): Fassungseintrag => ({
  ...original(), id: 3, sprache: "de", original: false, stand: "fertig", kapitel_fertig: 12, kapitel_gesamt: 12, gewaehlt: false, ...mehr,
});
const kapitel = (nr: number, stand: Kapitelstand["stand"], mehr: Partial<Kapitelstand> = {}): Kapitelstand => ({
  nr, titel: `Kapitel ${nr}`, stand, dauer_s: 600, geschaetzt: stand !== "fertig", bloecke: 10, fertig: stand === "fertig" ? 10 : 0, geprueft: 0,
  nachgearbeitet: 0, offen: 0, ...mehr,
});
const laufstand = (mehr: Partial<Laufstand> = {}): Laufstand => ({
  id: 3, stand: "laeuft", begonnen: "2026-11-26T11:13:00Z", bisher_s: 6720, noch_s: 4800, fertig_gegen: "2026-11-26T14:25:00Z",
  tempo_s_je_seite: 14, kapitel_jetzt: 3, block_jetzt: "3.5", stationen: [],
  kapitel: [kapitel(1, "fertig"), kapitel(2, "fertig"), kapitel(3, "laeuft", { fertig: 4 }), kapitel(4, "wartet")],
  zahlen: { bloecke: 40, uebersetzt: 24, bestanden: 22, nachgearbeitet: 2, offen: 1 }, grund: "", ...mehr,
});

/** Antworten nach Weg; jede Anfrage wird mit Methode und Körper gemerkt */
function server(antworten: (weg: string, methode: string, koerper: unknown) => [number, unknown]) {
  const anfragen: { weg: string; methode: string; koerper: unknown }[] = [];
  globalThis.fetch = vi.fn((weg: string, init?: RequestInit) => {
    const methode = init?.method ?? "GET";
    const koerper = init?.body ? JSON.parse(String(init.body)) : null;
    anfragen.push({ weg: String(weg), methode, koerper });
    const [status, inhalt] = antworten(String(weg), methode, koerper);
    return Promise.resolve(new Response(JSON.stringify(inhalt), { status }));
  }) as unknown as typeof fetch;
  return anfragen;
}

describe("Zeiten in Ortszeit und Dauer in Worten", () => {
  const jetzt = new Date(2026, 10, 26, 12, 0);
  const um = (tag: number, std: number, min: number) => new Date(2026, 10, tag, std, min).toISOString();

  it("nennt die Uhrzeit, morgen und andere Tage", () => {
    expect(zeitKurz(um(26, 15, 25), jetzt)).toBe("15:25");
    expect(zeitKurz(um(27, 3, 10), jetzt)).toBe("morgen 03:10");
    expect(zeitKurz(um(25, 22, 40), jetzt)).toBe("gestern 22:40");
    expect(zeitKurz(um(29, 8, 5), jetzt)).toBe("29.11., 08:05");
    expect(gegen(um(26, 15, 25), jetzt)).toBe("gegen 15:25");
    expect(gegen(um(27, 3, 10), jetzt)).toBe("morgen gegen 03:10");
    expect(zeitKurz(null)).toBe("");
  });

  it("schreibt Dauern aus und rundet Schätzungen", () => {
    expect(dauer(20)).toBe("unter 1 Minute");
    expect(dauer(60)).toBe("1 Minute");
    expect(dauer(6720)).toBe("1 Stunde 52 Minuten");
    expect(dauer(7200)).toBe("2 Stunden");
    expect(etwa(10_150)).toBe("2 Stunden 50 Minuten");
    expect(ungefaehr(10_800)).toBe("etwa 3 Stunden");
    expect(ungefaehr(10)).toBe("unter 1 Minute");
  });
});

describe("Text mit Marken", () => {
  it("zeigt Klammermarken als Text, Platzhalter als Zeichen und markiert die Stelle", () => {
    const t = "Rufe <x1/> auf, bevor du die <t2>Pumpe</t2> startest &amp; prüfe den Tank.";
    expect(stuecke(t, "Pumpe")).toEqual([
      { art: "text", text: "Rufe ", markiert: false }, { art: "platz", markiert: false },
      { art: "text", text: " auf, bevor du die ", markiert: false }, { art: "text", text: "Pumpe", markiert: true },
      { art: "text", text: " startest & prüfe den Tank.", markiert: false },
    ]);
    expect(klartext(t)).toBe("Rufe … auf, bevor du die Pumpe startest & prüfe den Tank.");
  });

  it("findet die Stelle auch, wenn sie über Marken oder geschützte Zeichen geht", () => {
    const t = "Der Preis ist Tempo: Jede Prüfung <t1>beschleunigt</t1> &amp; bremst.";
    const markiert = (s: string) => stuecke(t, s).filter((x) => x.art === "text" && x.markiert).map((x) => (x.art === "text" ? x.text : "")).join("");
    expect(markiert("<t1>beschleunigt</t1>")).toBe("beschleunigt");
    expect(markiert("& bremst")).toBe("& bremst");
    expect(markiert("gibt es nicht")).toBe("");
  });
});

describe("Wie eine Übersetzung heißt", () => {
  it("beschriftet die Flaggenlabels je Stand", () => {
    expect(labeltext(original(), 292)).toEqual({ name: "Englisch", stand: "Original, 292 Seiten" });
    expect(labeltext(deutsch(), 0)).toEqual({ name: "Deutsch", stand: "von uns übersetzt, fertig" });
    const fertigGegen = new Date(Date.now() + 3600_000).toISOString();
    const laeuft = labeltext(deutsch({ stand: "laeuft", kapitel_fertig: 7, fertig_gegen: fertigGegen }), 0).stand;
    expect(laeuft).toMatch(/^7 von 12 Kapiteln, fertig (morgen )?gegen \d\d:\d\d$/);
    expect(labeltext(deutsch({ stand: "laeuft", kapitel_fertig: 0, kapitel_gesamt: 0, fertig_gegen: fertigGegen }), 0).stand).toBe("beginnt");
    expect(labeltext(deutsch({ stand: "pause", kapitel_fertig: 3 }), 0).stand).toBe("Pause, 3 von 12 Kapiteln");
    expect(labeltext(deutsch({ stand: "teilweise", kapitel_fertig: 3 }), 0).stand).toBe("abgebrochen, 3 von 12 Kapiteln");
  });

  it("nennt Ort, Anteil und Dauer im Lauf und fasst wartende Kapitel zusammen", () => {
    const s = laufstand();
    expect(laufort(s)).toBe("Kapitel 3 von 4, Block 5 von 10");
    expect(laufanteil(s)).toBeCloseTo(24 / 40);
    expect(kapiteldauer(kapitel(4, "wartet", { dauer_s: 960 }))).toBe("etwa 16 Minuten");
    expect(kapiteldauer(kapitel(1, "fertig", { dauer_s: 840 }))).toBe("14 Minuten");
    const z = kapitelzeilen([kapitel(1, "fertig"), kapitel(2, "laeuft"), kapitel(3, "wartet"), kapitel(4, "wartet"), kapitel(5, "wartet")]);
    expect(z.einzeln.map((k) => k.nr)).toEqual([1, 2, 3]);
    expect(z.rest).toEqual({ von: 4, bis: 5, dauer_s: 1200 });
    expect(kapitelzeilen([kapitel(1, "fertig"), kapitel(2, "wartet"), kapitel(3, "wartet")]).rest).toBeNull();
  });

  it("zeigt vom Ort der Ablage nur den Dateinamen", () => {
    expect(stationstext({ name: "Setzen", stand: "fertig", text: "Abgelegt: /bestand/ab/cd/Fassungen/de/Roboter.epub" })).toBe("Abgelegt: Roboter.epub");
    expect(stationstext({ name: "Setzen", stand: "wartet", text: "" })).toBe("wartet");
  });

  it("benennt Befunde, Auftrag und Ergebnis", () => {
    expect(befundname({ art: "sinn", quelle: "ki", text: "", stelle: "" })).toBe("Sinn (KI-Prüfer)");
    expect(befundname({ art: "begriffe", quelle: "pruefung", text: "", stelle: "" })).toBe("Begriff");
    const l: Laufeintrag = { id: 3, buch_id: 7, titel: "Building Tiny Robots at Home", sprache: "de", stand: "pause", anteil: 0.5, kapitel_fertig: 4, kapitel_gesamt: 9, fertig_gegen: null, grund: "" };
    expect(auftragstext(l)).toBe("Pause, 4 von 9 Kapiteln");
    expect(auftragstext({ ...l, stand: "fehler", grund: "Die Leitstelle antwortet nicht" })).toBe("Fehler: Die Leitstelle antwortet nicht");
    expect(ergebnistext(laufstand({ stand: "fertig" }))).toBe("Fertig, 24 von 40 Blöcken deutsch, 1 offen");
  });
});

describe("Fassungen auf der Buchseite", () => {
  beforeEach(() => (anschluesse.jetzt = { ...anschluesse.jetzt, ki: true }));

  it("öffnen das Original unter /read und eine Übersetzung unter /read/de", () => {
    expect(fassungsAdresse(7, null)).toBe("/book/7/read");
    expect(fassungsAdresse(7, "de")).toBe("/book/7/read/de");
    expect(fassungsAdresse(7, "de", { restart: 1 })).toBe("/book/7/read/de?restart=1");
  });

  it("bieten das Übersetzen nur englischen EPUB und PDF ohne deutsche Fassung an, und nur mit KI", () => {
    expect(uebersetzbar(BUCH, [original()])).toBe(true);
    expect(uebersetzbar(BUCH, [original(), deutsch()])).toBe(false);
    expect(uebersetzbar({ ...BUCH, language: "de" }, [original()])).toBe(false);
    expect(uebersetzbar({ ...BUCH, file_format: "pdf" }, [original()])).toBe(true);
    expect(uebersetzbar({ ...BUCH, file_format: "mobi" }, [original()])).toBe(false);
    anschluesse.jetzt = { ...anschluesse.jetzt, ki: false };
    expect(uebersetzbar(BUCH, [original()])).toBe(false);
  });

  it("zeigen Labels, der laufenden mit Punkt, und schicken die Wahl an den Server", async () => {
    const anfragen = server((weg) => [200, weg.endsWith("/wahl") ? [original({ gewaehlt: false }), deutsch({ gewaehlt: true })] : { position: "", gelesen_am: null }]);
    const f = new Buchfassungen(7);
    f.liste = [original(), deutsch({ stand: "laeuft", kapitel_fertig: 7, fertig_gegen: new Date(Date.now() + 600_000).toISOString() })];
    render(Fassungslabels, { props: { buch: BUCH, fassungen: f } });
    const labels = screen.getAllByRole("button");
    expect(labels.map((b) => b.getAttribute("aria-pressed"))).toEqual(["true", "false"]);
    expect(labels[1].classList.contains("laeuft")).toBe(true);
    expect(labels[1].textContent).toContain("7 von 12 Kapiteln");
    await fireEvent.click(labels[1]);
    await vi.waitFor(() => expect(f.uebersetzung?.id).toBe(3));
    expect(anfragen.find((a) => a.methode === "PUT")).toEqual({ weg: "/api/books/7/fassungen/wahl", methode: "PUT", koerper: { sprache: "de" } });
  });

  it("zeigen ohne deutsche Fassung das Label zum Übersetzen, ohne alles nur das Original nicht", () => {
    const f = new Buchfassungen(7);
    f.liste = [original()];
    const { unmount } = render(Fassungslabels, { props: { buch: BUCH, fassungen: f } });
    expect(screen.getByRole("button", { name: /Ins Deutsche übersetzen/ })).toBeTruthy();
    unmount();
    render(Fassungslabels, { props: { buch: { ...BUCH, language: "de" }, fassungen: f } });
    expect(screen.queryByRole("group", { name: "Fassungen" })).toBeNull();
  });

  it("Lesen öffnet die gewählte Übersetzung mit ihrem eigenen Lesestand, dazu Prüfbericht und Begriffe", async () => {
    server(() => [200, { position: 'epub:{"percent":40}', gelesen_am: "2026-11-26T10:00:00Z" }]);
    const f = new Buchfassungen(7);
    f.liste = [original({ gewaehlt: false }), deutsch({ gewaehlt: true })];
    f.lesestand = { position: 'epub:{"percent":40}', gelesen_am: "2026-11-26T10:00:00Z" };
    render(Buchkopf, { props: { buch: BUCH, fassungen: f, onneu: () => {}, ongeaendert: () => {} } });
    const lesen = screen.getByRole("link", { name: /Weiterlesen, 40 %/ });
    expect(lesen.getAttribute("href")).toBe("/book/7/read/de");
    expect(screen.getByRole("link", { name: /Prüfbericht/ }).getAttribute("href")).toBe("/book/7/pruefbericht");
    expect(screen.getByRole("link", { name: /Begriffe/ }).getAttribute("href")).toBe("/book/7/begriffe");
    expect(screen.queryByRole("link", { name: /Auftrag/ })).toBeNull();
  });
});

describe("Rückfrage vor dem Übersetzen", () => {
  const folgen = { seiten: 344, kapitel: 12, bloecke: 1324, begriffe: 46, abbildungen: 23, dauer_s: 10_800, fertig_gegen: new Date(Date.now() + 10_800_000).toISOString(), tempo_s_je_seite: 30, ablage: { ort: "geraet", pfad: "/bestand/Fassungen/de/Roboter.epub" }, geht: true, grund: "" };

  it("nennt Umfang, Dauer, Ablauf und Ablage und startet mit der gewählten Anrede", async () => {
    const anfragen = server((weg, methode) => [200, methode === "POST" ? laufstand() : weg.includes("/folgen") ? folgen : []]);
    const gestartet = vi.fn();
    render(Uebersetzungsfrage, { props: { buch: BUCH, onschliessen: () => {}, ongestartet: gestartet } });
    await screen.findByText(/344 Seiten, 12 Kapitel/);
    expect(screen.getByText(/^etwa 3 Stunden mit Prüfung, fertig (morgen )?gegen/)).toBeTruthy();
    expect(screen.getByText("23 Bilder, wie im Original")).toBeTruthy();
    // Das Fenster ist in jsdom nicht offen (showModal fehlt): seine Tasten gelten als verborgen
    expect(screen.getByRole("button", { name: "du", hidden: true }).getAttribute("aria-pressed")).toBe("true");
    await fireEvent.click(screen.getByRole("button", { name: "Sie", hidden: true }));
    await fireEvent.click(screen.getByRole("button", { name: /^Übersetzen$/, hidden: true }));
    await vi.waitFor(() => expect(gestartet).toHaveBeenCalled());
    expect(anfragen.find((a) => a.methode === "POST")).toEqual({ weg: "/api/books/7/fassungen/de", methode: "POST", koerper: { anrede: "Sie" } });
  });

  it("nennt den Grund statt der Taste, wenn es nicht geht", async () => {
    server(() => [200, { ...folgen, geht: false, grund: "Das Format PDF wird noch nicht übersetzt, bisher nur EPUB" }]);
    render(Uebersetzungsfrage, { props: { buch: BUCH, onschliessen: () => {}, ongestartet: () => {} } });
    await screen.findByText("Das Format PDF wird noch nicht übersetzt, bisher nur EPUB");
    expect(screen.queryByRole("button", { name: /^Übersetzen$/, hidden: true })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Schließen", hidden: true })).toHaveLength(2);         // Zeichen oben und Taste unten
  });
});

describe("Übersetzungen unter Aufträge", () => {
  afterEach(() => uebersetzungen.halte());

  it("stehen mit Anteil und Pause da und nach dem Ende einmal mit dem Ergebnis", async () => {
    let laeufe: Laufeintrag[] = [{ id: 3, buch_id: 7, titel: "Building Tiny Robots at Home", sprache: "de", stand: "laeuft", anteil: 0.25, kapitel_fertig: 2, kapitel_gesamt: 9, fertig_gegen: null, grund: "" }];
    server((weg) => [200, weg === "/api/fassungen" ? laeufe : weg.endsWith("/stand") ? laufstand({ stand: "fertig" }) : {}]);
    await uebersetzungen.auffrischen();
    const a = auftraege.eigene.find((e) => e.id === "uebersetzung-3");
    expect(a).toMatchObject({ titel: "Übersetzen: Building Tiny Robots at Home", anteil: 0.25, laeuft: true, weg: "/book/7/uebersetzung" });
    expect(a?.text).toBe("2 von 9 Kapiteln");
    expect(typeof a?.pause).toBe("function");
    laeufe = [];
    await uebersetzungen.auffrischen();
    await vi.waitFor(() => expect(auftraege.eigene.find((e) => e.id === "uebersetzung-3")?.text).toBe("Fertig, 24 von 40 Blöcken deutsch, 1 offen"));
    expect(auftraege.eigene.find((e) => e.id === "uebersetzung-3")?.laeuft).toBe(false);
  });
});

describe("Offene Stelle im Prüfbericht", () => {
  const stelle: OffeneStelle = {
    kennung: "5.4", kapitel: 5, ort: "Testing Safely, Absatz 4", seite_original: null, seite_gedruckt: "",
    original: "The trade off is speed: every extra check slows the robot down.", deutsch: "Der Preis ist Tempo: Jede Prüfung beschleunigt den Roboter.",
    befunde: [{ art: "sinn", quelle: "ki", text: '"slows down" heißt hier "bremst".', stelle: "beschleunigt" }],
  };

  it("zeigt beide Sprachen mit markierter Stelle und Befund", () => {
    render(Offenestelle, { props: { stelle, fassung: 3, onerledigt: () => {} } });
    expect(document.querySelector("mark")?.textContent).toBe("beschleunigt");
    expect(screen.getByText(/Sinn \(KI-Prüfer\)/)).toBeTruthy();
    expect(screen.queryByText(/im Original$/)).toBeNull();
  });

  it("nennt bei einem PDF die gedruckte Seite im Original", () => {
    render(Offenestelle, { props: { stelle: { ...stelle, seite_original: 31, seite_gedruckt: "29" }, fassung: 3, onerledigt: () => {} } });
    expect(screen.getByText("Seite 29 im Original")).toBeTruthy();
  });

  it("nimmt einen Text von Hand nur, wenn er die festen Prüfungen besteht", async () => {
    let bestanden = false;
    const anfragen = server(() => (bestanden ? [200, { kennung: "5.4", stand: "gesetzt", deutsch: "x", befunde: [] }] : [422, { detail: "Der Text besteht die festen Prüfungen nicht: zu kurz", befunde: [{ art: "laenge", quelle: "pruefung", text: "Die Übersetzung ist auffällig kürzer", stelle: "" }] }]));
    const erledigt = vi.fn();
    render(Offenestelle, { props: { stelle, fassung: 3, onerledigt: erledigt } });
    await fireEvent.click(screen.getByRole("button", { name: /Bearbeiten/ }));
    const feld = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(feld.value).toBe(stelle.deutsch);
    await fireEvent.input(feld, { target: { value: "Zu kurz." } });
    await fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await screen.findByText("Der Text besteht die festen Prüfungen nicht");
    expect(screen.getByText(/Die Übersetzung ist auffällig kürzer/)).toBeTruthy();
    expect(erledigt).not.toHaveBeenCalled();
    bestanden = true;
    await fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await vi.waitFor(() => expect(erledigt).toHaveBeenCalled());
    expect(anfragen.at(-1)).toEqual({ weg: "/api/fassungen/3/bloecke/5.4", methode: "POST", koerper: { aktion: "setzen", text: "Zu kurz." } });
  });
});

describe("Lesen der Übersetzung", () => {
  const uebersetzung = uebersetzungsfassung(BUCH, deutsch() as Fassungseintrag & { id: number }, { position: 'epub:{"percent":40}', gelesen_am: null });

  it("öffnet die Datei der Übersetzung mit ihrem eigenen Lesestand, ohne Stellen", () => {
    expect(uebersetzung).toMatchObject({ fassung: 3, sprache: "de", format: "epub", datei: "/api/fassungen/3/datei", position: 'epub:{"percent":40}', mitStellen: false });
    expect(uebersetzung.ort.pfad).toBe("/book/7/read/de");
    expect(originalfassung(BUCH)).toMatchObject({ fassung: null, datei: "/api/books/7/file", position: 'epub:{"percent":25}', mitStellen: true });
  });

  it("liest die Übersetzung eines PDF im EPUB-Leser", async () => {
    const pdf = { ...BUCH, file_format: "pdf", file_name: "Roboter.pdf" };
    server((weg) => [200, weg.endsWith("/fassungen") ? [original(), deutsch()] : { position: "", gelesen_am: null }]);
    expect(await ladeLesefassung(pdf, "de")).toMatchObject({ fassung: 3, format: "epub", datei: "/api/fassungen/3/datei", mitStellen: false });
    expect(await ladeLesefassung(pdf, undefined)).toMatchObject({ fassung: null, format: "pdf", mitStellen: true });
  });

  it("merkt die Stelle bei der Übersetzung, nie am Original", () => {
    const anfragen = server(() => [200, {}]);
    const aktualisiere = vi.spyOn(buecher, "aktualisiere");
    const s = new Positionsspeicher(uebersetzung.ort, "epub");
    s.merke({ percent: 41 });
    s.sofort();
    expect(anfragen).toEqual([{ weg: "/api/fassungen/3/leseposition", methode: "PATCH", koerper: { position: 'epub:{"percent":41}' } }]);
    expect(aktualisiere).not.toHaveBeenCalled();
    aktualisiere.mockRestore();
  });

  it("lädt und legt dort keine Notizen, Markierungen oder Etiketten an", async () => {
    const anfragen = server(() => [200, []]);
    const sitzung = new Lesesitzung({ ...BUCH, file_format: "md" }, uebersetzung);
    await sitzung.laden();
    await sitzung.markiere({ text: "Roboter", cfi: "epubcfi(/6/4)", x: 0, oben: 0, unten: 0, ort: "" } as never, "#ffcc00");
    expect(await sitzung.neueNotiz("Notiz")).toBe(false);
    expect(sitzung.mitEtiketten).toBe(false);
    expect(anfragen).toEqual([]);
  });
});
