// BF-82: Ersteinrichtung nach einer Neuinstallation. Ablauf und Fortschritt, Sätze der Folgen, Hochladen der Sicherung in
// Teilen, Zurück und Weiter im Assistenten, Willkommen und das Ende unter Wartung. Alle Namen und Adressen sind erfunden.
import { fireEvent, render, screen } from "@testing-library/svelte";
import Aenderungen from "../src/ansichten/einrichtung/Aenderungen.svelte";
import Willkommen from "../src/ansichten/einrichtung/Willkommen.svelte";
import { ApiError } from "../src/lib/api/client";
import type { Anschluss, Einrichtung, Hochladestand, Persoenlichfolgen, Schritt, Sicherung, Wiederherstellfolgen } from "../src/lib/api/einrichtung";
import { aktueller, fortschritt, katalogwahlAus, lagetitel, nachbar, schritttitel, sichtbar, uebersicht, zeigtPflicht } from "../src/lib/einrichtung/ablauf";
import {
  aenderungenZahl, auftragszahl, papierkorbText, persoenlichAusFolgen, persoenlichEinFolgen, sicherungszeile, uebernehmensfolgen, umzugGilt, wiederherstellfolgen,
} from "../src/lib/einrichtung/saetze";
import { ladeSicherungHoch, type Sicherungsdienst } from "../src/lib/einrichtung/sicherungslader";
import { einrichtung } from "../src/lib/stand/einrichtung.svelte";
import { rueckfrage } from "../src/lib/stand/rueckfrage.svelte";

const schritt = (schluessel: string, stand: Schritt["stand"] = "offen", pflicht = false, text = ""): Schritt => ({ schluessel, name: schluessel, pflicht, stand, text, weiter: true, grund: "" });

const NEU = [schritt("konto", "erledigt", true), schritt("orte", "erledigt", true), schritt("anschluesse"), schritt("katalog"), schritt("familie"), schritt("buecher"), schritt("abschluss", "offen", true)];

function zustand(ueber: Partial<Einrichtung> = {}): Einrichtung {
  return { modus: "neu", zeigen: true, ausgangslage: "neu", schritt: "anschluesse", schritte: NEU, ausgangslagen: [], konto: true, anmeldung: "eigen", aenderungen: 0, begonnen_am: null, abgeschlossen_am: null, ...ueber };
}

function server(antwort: (weg: string, art: string, inhalt: unknown) => unknown) {
  const f = vi.fn((weg: string, o: RequestInit = {}) =>
    Promise.resolve(new Response(JSON.stringify(antwort(weg, o.method ?? "GET", o.body ? JSON.parse(String(o.body)) : null)), { status: 200 })));
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

afterEach(() => {
  einrichtung.nimm(null as unknown as Einrichtung);
  einrichtung.gezeigt = "";
  einrichtung.willkommen = false;
  rueckfrage.antworte(false);
});

describe("Ablauf und Fortschritt", () => {
  it("zeigt bei Neu beginnen sechs Stationen, die gezeigte als jetzt, davor fertig", () => {
    const f = fortschritt("neu", NEU, "anschluesse");
    expect(f.stationen.map((s) => s.name)).toEqual(["Konto", "Orte", "Anschlüsse", "Katalog", "Familie", "Bücher"]);
    expect(f.stationen.map((s) => s.art)).toEqual(["fertig", "fertig", "jetzt", "", "", ""]);
    expect(f.nummer).toBe(3);
    expect(f.fertig).toBe(false);
  });

  it("steht am Abschluss ganz auf fertig, übersprungene gestrichelt", () => {
    const schritte = NEU.map((s) => (s.schluessel === "katalog" ? { ...s, stand: "uebersprungen" as const } : s));
    const f = fortschritt("neu", schritte, "abschluss");
    expect(f.fertig).toBe(true);
    expect(f.nummer).toBeNull();
    expect(f.stationen.find((s) => s.schluessel === "katalog")?.art).toBe("wartet");
    expect(schritttitel("neu", "abschluss")).toBe("Fertig");
  });

  it("nennt den Bericht als letzte Station beim Wiederherstellen, beim Umzug fällt Originale mit Kellerwolke weg", () => {
    const sicherung = [schritt("orte", "erledigt", true), schritt("sicherung", "erledigt", true), schritt("pruefung", "erledigt", true), schritt("abschluss", "offen", true)];
    const f = fortschritt("sicherung", sicherung, "abschluss");
    expect(f.stationen.map((s) => s.name)).toEqual(["Orte", "Sicherung", "Prüfen", "Bericht"]);
    expect(f.nummer).toBe(4);
    expect(schritttitel("sicherung", "abschluss")).toBe("Bericht");
    const umzug = [schritt("verbinden", "erledigt", true), schritt("orte", "offen", true), schritt("originale", "entfaellt", true), schritt("pruefung", "offen", true), schritt("abschluss", "offen", true)];
    expect(sichtbar(umzug).map((s) => s.schluessel)).toEqual(["verbinden", "orte", "pruefung", "abschluss"]);
    expect(fortschritt("umzug", umzug, "orte").stationen.map((s) => s.name)).toEqual(["Verbinden", "Orte", "Übernahme"]);
    expect(nachbar(sichtbar(umzug), "orte", 1)).toBe("pruefung");
  });

  it("zeigt den gewählten Schritt, sonst den ersten offenen, und Pflicht nur, wo sich anderes überspringen lässt", () => {
    expect(aktueller(NEU, "katalog", "anschluesse")?.schluessel).toBe("katalog");
    expect(aktueller(NEU, "", "anschluesse")?.schluessel).toBe("anschluesse");
    expect(aktueller(NEU, "fremd", null)?.schluessel).toBe("abschluss");
    expect(nachbar(NEU, "konto", -1)).toBeNull();
    expect(zeigtPflicht(NEU, NEU[1])).toBe(true);
    expect(zeigtPflicht(NEU, NEU[6])).toBe(false);
    const sicherung = [schritt("orte", "offen", true), schritt("sicherung", "offen", true)];
    expect(zeigtPflicht(sicherung, sicherung[0])).toBe(false);
    expect(lagetitel("umzug")).toBe("Umzug von anderer Installation");
    expect(lagetitel("wartung")).toBe("Einrichtung");
    expect(katalogwahlAus("Leer begonnen")).toBe("leer");
    expect(katalogwahlAus("anders")).toBeNull();
  });

  it("listet am Ende jeden Anschluss einzeln, ohne Adresse unter den übersprungenen", () => {
    const anschluesse = [
      { art: "kellerwolke", name: "Kellerwolke", adresse: "https://wolke.probe.test" },
      { art: "leitstelle", name: "Leitstelle", adresse: "" },
    ] as Anschluss[];
    const schritte = NEU.map((s) => (s.schluessel === "anschluesse" ? { ...s, stand: "erledigt" as const } : s.schluessel === "buecher" ? { ...s, stand: "uebersprungen" as const, text: "Übersprungen, später unter Einstellungen" } : s));
    const u = uebersicht(schritte, anschluesse);
    expect(u.eingerichtet.map((z) => z.name)).toEqual(["konto", "orte", "Kellerwolke"]);
    expect(u.uebersprungen.map((z) => [z.name, z.text])).toEqual([["Leitstelle", "nicht eingerichtet"], ["katalog", ""], ["familie", ""], ["buecher", "Übersprungen, später unter Einstellungen"]]);
    expect(u.eingerichtet[0].ziel).toBeNull();
    expect(u.eingerichtet[2].ziel).toEqual(["Verbindungen", "/settings/verbindungen"]);
    const ohne = uebersicht(NEU, anschluesse.map((a) => ({ ...a, adresse: "" })));
    expect(ohne.uebersprungen.find((z) => z.schluessel === "anschluesse")?.text).toBe("Kellerwolke, Leitstelle");
  });
});

describe("Sätze der Folgen", () => {
  const sicherung: Sicherung = { quelle: "geraet", kennung: "s.zip", name: "s.zip", groesse: 184_000_000, angelegt_am: "2026-11-26T03:00:00Z", buecher: 4731, profile: 4, version: "0.42.1" };

  it("nennt je Sicherung Datum, Größe, Bücher und Profile, ohne was fehlt", () => {
    expect(sicherungszeile(sicherung)).toMatch(/^26\.11\.2026, \d\d:00, 184 MB, 4\.731 Bücher, 4 Profile$/);
    expect(sicherungszeile({ ...sicherung, angelegt_am: null, buecher: null, profile: 1 })).toBe("184 MB, 1 Profil");
  });

  it("sagt vor dem Einspielen, dass nichts gelöscht wird, und nennt, was ersetzt wird", () => {
    const leer: Wiederherstellfolgen = { sicherung, ersetzt: [], vorher_sichern: false, stand: "a" };
    expect(wiederherstellfolgen(leer)).toContain("Hier liegt noch nichts: Es wird nichts überschrieben und nichts gelöscht.");
    const laufend = wiederherstellfolgen({ ...leer, ersetzt: ["Der Bestand mit 12 Büchern wird durch den der Sicherung ersetzt"], vorher_sichern: true }, true);
    expect(laufend).toContain("Der Bestand mit 12 Büchern wird durch den der Sicherung ersetzt.");
    expect(laufend.filter((s) => s.startsWith("Vorher entsteht"))).toHaveLength(1);
    expect(laufend.at(-1)).toBe("Gelöscht wird nichts.");
    const vomServer = wiederherstellfolgen({ ...leer, ersetzt: ["Vorher entsteht eine Sicherung des jetzigen Stands im Sicherungsordner"], vorher_sichern: true }, true);
    expect(vomServer.filter((s) => s.startsWith("Vorher entsteht"))).toEqual(["Vorher entsteht eine Sicherung des jetzigen Stands im Sicherungsordner."]);
    expect(laufend.some((s) => s.includes("Hier liegt noch nichts"))).toBe(false);
  });

  it("zählt Änderungen in Worten und nennt jede vor dem Übernehmen", () => {
    expect(aenderungenZahl(1)).toBe("Eine Änderung");
    expect(aenderungenZahl(2)).toBe("Zwei Änderungen");
    expect(aenderungenZahl(20)).toBe("20 Änderungen");
    expect(uebernehmensfolgen([{ id: "a", schritt: "familie", art: "profil", was: "Neues Profil Mia (Kind)", alt: "", neu: "Mia" }])).toEqual(["Neues Profil Mia (Kind).", "Alles andere bleibt, wie es ist. Gelöscht wird nichts."]);
    expect(auftragszahl({ fertig: 2934, gesamt: 4731 }, "geprüft")).toBe("2.934 von 4.731 geprüft");
    expect(umzugGilt(null)).toBe("für einen Umzug");
    expect(umzugGilt("2026-11-26T19:46:00Z")).toMatch(/^bis \d\d:46 Uhr, für einen Umzug$/);
  });

  it("zeigt vor dem Schalten, was in die Kellerwolke kommt und was dort bleibt", () => {
    const f: Persoenlichfolgen = { buecher: 3, profile_datei: "Apps/BücherFreunde/profile.json", profile: [], lesestaende: 2, vorlesestellen: 0, notizen: 1, markierungen: 0, etiketten: 0, private: 0, freigaben: 0, stand: "x" };
    expect(persoenlichEinFolgen(f)[0]).toBe("3 Bücher bekommen in der Kellerwolke eine kleine Datei mit dem Persönlichen je Profil: 2 Lesestände, 1 Notiz.");
    expect(persoenlichAusFolgen(f)[1]).toMatch(/Die vorhandenen 3 Dateien und die Datei der Profile bleiben dort/);
    expect(papierkorbText(f)).toBe("3 Dateien und die Datei der Profile in den Papierkorb der Kellerwolke (dort zurückzuholen)");
    expect(papierkorbText({ ...f, buecher: 0 })).toMatch(/^Die Datei der Profile/);
  });
});

describe("Sicherung in Teilen hochladen", () => {
  const stand = (empfangen: number, fertig = false): Hochladestand => ({ id: "h1", name: "s.zip", groesse: 10, sha256: "ab", empfangen, teil_groesse: 4, fertig });

  it("lädt Teil für Teil ab dem Stand des Servers und folgt einem anderen Stand (409)", async () => {
    const teile: [number, number][] = [];
    let erstes = true;
    const dienst: Sicherungsdienst = {
      anmelden: async () => stand(0),
      teil: async (_id, ab, teil) => {
        teile.push([ab, teil.size]);
        if (erstes) {
          erstes = false;
          throw new ApiError(409, "anderer Stand", { empfangen: 4 });
        }
        return stand(ab + teil.size, ab + teil.size >= 10);
      },
      stand: async () => stand(0),
    };
    const meldungen: string[] = [];
    const h = await ladeSicherungHoch(new File(["0123456789"], "s.zip"), dienst, async () => "ab", (s) => meldungen.push(s.lage), new AbortController().signal);
    expect(h.fertig).toBe(true);
    expect(teile).toEqual([[0, 4], [4, 4], [8, 2]]);
    expect(meldungen[0]).toBe("prueft");
    expect(meldungen.at(-1)).toBe("fertig");
  });

  it("wartet nach einem Abriss und fragt den Stand neu; eine falsche Prüfsumme (422) geht hinaus", async () => {
    let versuch = 0;
    const gewartet: number[] = [];
    const dienst: Sicherungsdienst = {
      anmelden: async () => stand(0),
      teil: async (_id, ab, teil) => {
        if (versuch++ === 0) throw new ApiError(0, "Keine Verbindung");
        if (ab + teil.size >= 10) throw new ApiError(422, "Die Prüfsumme stimmt nicht");
        return stand(ab + teil.size);
      },
      stand: async () => stand(4),
    };
    await expect(ladeSicherungHoch(new File(["0123456789"], "s.zip"), dienst, async () => "ab", () => {}, new AbortController().signal, { pausenMs: [5], warte: async (ms) => void gewartet.push(ms) }))
      .rejects.toThrow("Die Prüfsumme stimmt nicht");
    expect(gewartet).toEqual([5]);
  });
});

describe("Zurück und Weiter", () => {
  it("merkt Weiter in der Ersteinrichtung am Server und zeigt den nächsten Schritt", async () => {
    const f = server((weg, art) => (art === "POST" && weg === "/api/einrichtung/schritte/anschluesse" ? zustand({ schritt: "katalog", schritte: NEU.map((s) => (s.schluessel === "anschluesse" ? { ...s, stand: "erledigt" } : s)) }) : {}));
    einrichtung.nimm(zustand());
    expect(einrichtung.schritt?.schluessel).toBe("anschluesse");
    await einrichtung.weiter();
    expect(f).toHaveBeenCalledWith("/api/einrichtung/schritte/anschluesse", expect.objectContaining({ method: "POST", body: JSON.stringify({ aktion: "erledigt" }) }));
    expect(einrichtung.schritt?.schluessel).toBe("katalog");
    einrichtung.zurueck();
    expect(einrichtung.schritt?.schluessel).toBe("anschluesse");
  });

  it("geht vom ersten Schritt zurück zu den Ausgangslagen; ein erledigter Schritt geht ohne Anfrage weiter", async () => {
    const f = server(() => ({}));
    einrichtung.nimm(zustand());
    einrichtung.zeige("konto");
    einrichtung.zurueck();
    expect(einrichtung.zeigtWillkommen).toBe(true);
    einrichtung.zeige("orte");
    await einrichtung.weiter();
    expect(f).not.toHaveBeenCalled();
    expect(einrichtung.schritt?.schluessel).toBe("anschluesse");
  });

  it("merkt unter Wartung nichts am Server und bleibt am ersten Schritt stehen", async () => {
    const f = server(() => ({}));
    const wartung = ["orte", "anschluesse", "katalog", "familie", "buecher", "abschluss"].map((s) => schritt(s, "offen", s === "orte" || s === "abschluss"));
    einrichtung.nimm(zustand({ modus: "wartung", ausgangslage: null, schritt: "orte", schritte: wartung }));
    expect(einrichtung.ersteinrichtung).toBe(false);
    await einrichtung.ueberspringen();
    expect(einrichtung.schritt?.schluessel).toBe("anschluesse");
    einrichtung.zurueck();
    einrichtung.zurueck();
    expect(einrichtung.schritt?.schluessel).toBe("orte");
    expect(einrichtung.zeigtWillkommen).toBe(false);
    expect(f).not.toHaveBeenCalled();
  });
});

describe("Ansichten", () => {
  it("zeigt die vier Ausgangslagen; ein Tipp wählt am Server", async () => {
    const f = server((weg) => (weg === "/api/einrichtung/ausgangslage" ? zustand({ ausgangslage: "umzug", schritt: "verbinden", schritte: [schritt("verbinden", "offen", true)] }) : {}));
    einrichtung.nimm(zustand({ ausgangslage: null, schritt: null, schritte: [] }));
    render(Willkommen);
    expect(screen.getAllByRole("button").map((b) => b.querySelector("b")?.textContent)).toEqual([
      "Neu beginnen", "Aus Sicherung wiederherstellen", "Ablage in der Kellerwolke übernehmen", "Umzug von anderer Installation",
    ]);
    await fireEvent.click(screen.getByText("Umzug von anderer Installation"));
    await vi.waitFor(() => expect(einrichtung.lauf).toBe("umzug"));
    expect(f).toHaveBeenCalledWith("/api/einrichtung/ausgangslage", expect.objectContaining({ body: JSON.stringify({ ausgangslage: "umzug" }) }));
  });

  it("übernimmt unter Wartung nur, was angehakt ist, nach der Rückfrage mit jeder Änderung", async () => {
    const liste = {
      aenderungen: [
        { id: "a1", schritt: "anschluesse", art: "anschluss", was: "Nachschlag: Adresse https://nachschlag.probe.test", alt: "", neu: "https://nachschlag.probe.test" },
        { id: "a2", schritt: "familie", art: "profil", was: "Neues Profil Mia (Kind)", alt: "", neu: "Mia" },
      ],
      unveraendert: ["Speicherorte", "Katalog"],
      stand: "st1",
    };
    const f = server((weg) => (weg === "/api/einrichtung/aenderungen" ? liste : weg === "/api/einrichtung/uebernehmen" ? { uebernommen: [liste.aenderungen[1]], verworfen: 1 } : zustand({ modus: "aus", zeigen: false })));
    einrichtung.nimm(zustand({ modus: "wartung", ausgangslage: null, schritt: "abschluss", schritte: [schritt("abschluss", "offen", true)] }));
    render(Aenderungen);
    await screen.findByText("Zwei Änderungen. Übernommen wird nur, was angehakt ist.");
    await fireEvent.click(screen.getByText("Nachschlag: Adresse https://nachschlag.probe.test"));
    await fireEvent.click(screen.getByText("Übernehmen (1)"));
    await vi.waitFor(() => expect(rueckfrage.offen?.titel).toBe("Eine Änderung übernehmen?"));
    expect(rueckfrage.offen?.folgen).toEqual(["Neues Profil Mia (Kind).", "Alles andere bleibt, wie es ist. Gelöscht wird nichts."]);
    rueckfrage.antworte(true);
    await vi.waitFor(() => expect(f).toHaveBeenCalledWith("/api/einrichtung/uebernehmen", expect.objectContaining({ body: JSON.stringify({ stand: "st1", ids: ["a2"] }) })));
  });
});
