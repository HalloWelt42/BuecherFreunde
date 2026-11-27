// Familie mit Profilen (BF-78): Profilschlüssel im Kopf, Start mit und ohne Wahl, Rechte an einer Stelle, Reiter, Freigaben,
// Texte des Elternbereichs, Bild-PIN. Nur erfundene Namen und Titel.
import { fireEvent, render, screen } from "@testing-library/svelte";
import { ApiError, get, del, geraetKennung, getProfil, onAuthError, onProfilFehlt, post, setProfil } from "../src/lib/api/client";
import type { Familie, Ich, Profil, Stufenangabe, Zugang } from "../src/lib/api/familie";
import {
  alterHinweis, alterText, einblickHinweis, einblickZeile, einstellungenVon, lesezeitVorgabe, pinGueltig, pinText, profilZeile, rollenText, stufeVorschlag,
  tempoText, vorgabeText,
} from "../src/lib/familie";
import { anschluesse } from "../src/lib/stand/anschluesse.svelte";
import { familie } from "../src/lib/stand/familie.svelte";
import { ich } from "../src/lib/stand/ich.svelte";
import { reiterAus, sichtbareReiter } from "../src/ansichten/einstellungen/reiter";
import { setze } from "../src/ansichten/einstellungen/familie/aendern";
import { freigabeziel, zielAus } from "../src/ansichten/zuordnen/ziel";
import { Zuordnung } from "../src/ansichten/zuordnen/zuordnung.svelte";
import Bildpinfeld from "../src/lib/teile/Bildpinfeld.svelte";
import Ansagestimme from "../src/ansichten/einstellungen/familie/Ansagestimme.svelte";
import type { Buch } from "../src/lib/typen";

const STUFEN: Stufenangabe[] = [
  { schluessel: "vorlesen", name: "Vorlesen", alter_von: 0, alter_bis: 6, faehigkeiten: ["lesen"], einblick: ["titel", "lesezeit", "fortschritt"] },
  { schluessel: "erstes_lesen", name: "Erstes Lesen", alter_von: 7, alter_bis: 7, faehigkeiten: ["lesen"], einblick: ["titel", "lesezeit", "fortschritt"] },
  { schluessel: "lesen_lernen", name: "Lesen und Lernen", alter_von: 8, alter_bis: 9, faehigkeiten: ["lesen"], einblick: ["titel", "lesezeit", "fortschritt"],
    vorgaben: { lesehilfen: { mitlesen: true, tempo: 1, silben: true, lesezeile: true, schrift: "gross", schrift_wahl: "normal", hinweise_sprechen: true, tasten_ansagen: true }, gestaltung: "gross", uhr: "zeiger" } },
  { schluessel: "schule", name: "Schule", alter_von: 10, alter_bis: 13, faehigkeiten: ["lesen"], einblick: ["titel", "grober_fortschritt"] },
  { schluessel: "jugend", name: "Jugend", alter_von: 14, alter_bis: null, faehigkeiten: ["lesen"], einblick: ["titel", "grober_fortschritt", "geteiltes"] },
];
const ZUGANG: Zugang = { pin_stellen_von: 4, pin_stellen_bis: 8, bild_pin_anzahl: 3, bilder: ["apfel", "ball", "baum", "mond", "sonne", "stern"] };

const profil = (mehr: Partial<Profil> = {}): Profil => ({ id: "p-1", name: "Wiebke", zeichen: "feather", farbe: "#6366f1", rolle: "verwaltung", stufe: null, hat_pin: true, hat_bild_pin: false, ...mehr });
const KIND = profil({ id: "k-1", name: "Joris", rolle: "kind", stufe: "lesen_lernen", hat_pin: false, hat_bild_pin: true, geburtsjahr: 2017 });

function ichAls(p: Profil, faehigkeiten: Ich["faehigkeiten"]): Ich {
  return {
    profil: p, faehigkeiten, darstellung: {}, lesehilfen: null, einblick: [], katze: { an: false, name: "", schnurren: false },
    lesezeit: { an: false, heute_s: 0, grenze_s: null, rest_s: null, ruht: false, ruhe_bis: null, hinweis_ab_s: null }, gestaltung: null, uhr: null,
    vorlesen: { stimme: "", werte: {}, eigene_wahl: p.rolle !== "kind" },
  };
}

function buch(id: number, title: string, mehr: Partial<Buch> = {}): Buch {
  return {
    id, hash: "", title, author: "Tilda Brombeer", publisher: "", file_format: "epub", file_size: 1, cover_path: "", page_count: 0, year: null, isbn: "", typ: "", gattung: "",
    umschlag: "gestaltet", umschlag_schlicht: false, umschlag_wahl: "", sammlung_id: null, band_nummer: "", is_favorite: false, is_to_read: false, rating: 0,
    reading_position: "", last_read_at: null, categories: [], sammlung: null, created_at: "", updated_at: "", ...mehr,
  };
}

/** Antworten je Weg. Ein Abruf (GET) eines Wegs, den der Test nicht nennt, gibt es nicht (404), wie beim echten Server; so
 *  bekommt etwa das Nachladen des Bestands nach einem Profilwechsel keine fremde Antwort. Schreibende Wege antworten leer. */
function server(wege: Record<string, unknown>) {
  const f = vi.fn((weg: string, init?: RequestInit) => {
    const pfad = weg.split("?")[0];
    if (pfad === "/api/familie/stufen" && !(pfad in wege)) return Promise.resolve(new Response(JSON.stringify({ stufen: STUFEN, lesezeit: [], zugang: ZUGANG })));
    if (!(pfad in wege) && (init?.method ?? "GET") === "GET") return Promise.resolve(new Response(JSON.stringify({ detail: "Nicht gefunden" }), { status: 404 }));
    return Promise.resolve(new Response(JSON.stringify(wege[pfad] ?? {}), { status: 200 }));
  });
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

const kopf = (f: ReturnType<typeof server>, n: number) => (f.mock.calls[n] as unknown as [string, RequestInit])[1].headers as Record<string, string>;

afterEach(() => {
  ich.setze(null);
  setProfil("");
});

describe("Profilschlüssel im Kopf", () => {
  it("schickt den gemerkten Schlüssel als X-Profil und die Kennung des Geräts als X-Geraet", async () => {
    const f = server({ "/api/test": { ok: true } });
    setProfil("schluessel-1");
    await get("/api/test");
    expect(kopf(f, 0)["X-Profil"]).toBe("schluessel-1");
    expect(kopf(f, 0)["X-Geraet"]).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(geraetKennung()).toBe(kopf(f, 0)["X-Geraet"]);
  });

  it("schickt ohne Wahl keinen Profilkopf und vergisst den Schlüssel beim Wechsel", async () => {
    const f = server({ "/api/test": {} });
    setProfil("alt");
    setProfil("");
    expect(getProfil()).toBe("");
    await get("/api/test");
    expect(kopf(f, 0)["X-Profil"]).toBeUndefined();
  });

  it("führt bei 401 profil_waehlen zur Profilwahl und meldet das Gerät nicht ab", async () => {
    const abmelden = vi.fn();
    const waehlen = vi.fn();
    onAuthError(abmelden);
    onProfilFehlt(waehlen);
    const antwort = (status: number, daten: unknown, kopf: Record<string, string> = {}) =>
      (globalThis.fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(daten), { status, headers: kopf }))) as unknown as typeof fetch);
    antwort(401, { detail: "Bitte zuerst ein Profil wählen", code: "profil_waehlen" }, { "WWW-Authenticate": "Profil" });
    await expect(get("/api/books")).rejects.toBeInstanceOf(ApiError);
    expect(waehlen).toHaveBeenCalledTimes(1);
    expect(abmelden).not.toHaveBeenCalled();
    antwort(401, { detail: "Anmeldung erforderlich" }, { "WWW-Authenticate": "Bearer" });
    await expect(get("/api/books")).rejects.toBeInstanceOf(ApiError);
    expect(abmelden).toHaveBeenCalledTimes(1);
    // PIN vergessen mit falschem Kennwort: 403 mit Grund, das Gerät bleibt angemeldet
    antwort(403, { detail: "Name oder Kennwort stimmt nicht" });
    await expect(post("/api/familie/profile/x/pin/vergessen", {})).rejects.toBeInstanceOf(ApiError);
    expect(abmelden).toHaveBeenCalledTimes(1);
  });

  it("nimmt Antworten ohne Inhalt (204) an", async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(new Response(null, { status: 204 }))) as unknown as typeof fetch;
    await expect(post("/api/familie/verlassen")).resolves.toBeUndefined();
  });

  it("sendet beim Zurücknehmen die Angaben mit", async () => {
    const f = server({ "/api/weg": {} });
    await del("/api/weg", { art: "buch", ziel_ids: [3] });
    const [, optionen] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(optionen.method).toBe("DELETE");
    expect(JSON.parse(String(optionen.body))).toEqual({ art: "buch", ziel_ids: [3] });
  });
});

describe("Start mit Profilen", () => {
  const OHNE_GERAET = { gebunden_an: null, fest_auf: null, offen: false };
  const familieMit = (mehr: Partial<Familie>): Familie => ({ profile: [profil()], braucht_wahl: false, aktiv: null, geraet: OHNE_GERAET, stimme: "", ...mehr });

  it("geht mit einem gültigen gemerkten Schlüssel gleich weiter", async () => {
    setProfil("gilt-noch");
    const f = server({ "/api/familie": familieMit({ braucht_wahl: true, aktiv: "p-1", profile: [profil(), KIND] }), "/api/familie/ich": ichAls(profil(), ["lesen"]) });
    await familie.starte();
    expect(familie.phase).toBe("bereit");
    expect(getProfil()).toBe("gilt-noch");
    expect(f.mock.calls.some(([w]) => w === "/api/familie/wahl")).toBe(false);
  });

  it("holt mit nur einem Profil ohne PIN trotzdem einen Schlüssel und geht weiter", async () => {
    const einzig = profil({ hat_pin: false });
    const f = server({ "/api/familie": familieMit({ profile: [einzig] }), "/api/familie/wahl": { schluessel: "neu-1", profil: ichAls(einzig, ["lesen"]) } });
    await familie.starte();
    expect(familie.phase).toBe("bereit");
    expect(getProfil()).toBe("neu-1");
    expect(ich.profil?.name).toBe("Wiebke");
    // Das Cookie für Bilder und Ströme setzt die Wahl selbst
    expect(f.mock.calls.some(([w]) => w === "/api/anmeldung/zugang")).toBe(false);
  });

  it("zeigt die Wahl, wenn der Server sie verlangt, und vergisst den alten Schlüssel", async () => {
    setProfil("abgelaufen");
    server({ "/api/familie": familieMit({ braucht_wahl: true, profile: [profil(), KIND] }) });
    await familie.starte();
    expect(familie.phase).toBe("wahl");
    expect(getProfil()).toBe("");
    expect(familie.waehlbar.map((p) => p.name)).toEqual(["Wiebke", "Joris"]);
  });

  it("öffnet auf einem gebundenen Gerät gleich das Kind, mit Bild-PIN nur dieses zur Wahl", async () => {
    const ohneBild = { ...KIND, hat_bild_pin: false };
    const gebunden = { gebunden_an: "k-1", fest_auf: "k-1", offen: false };
    server({ "/api/familie": familieMit({ braucht_wahl: true, profile: [ohneBild], geraet: gebunden }), "/api/familie/wahl": { schluessel: "kind-1", profil: ichAls(ohneBild, ["lesen"]) } });
    await familie.starte();
    expect(familie.phase).toBe("bereit");
    expect(ich.istKind).toBe(true);
    const f = server({ "/api/familie": familieMit({ braucht_wahl: true, profile: [KIND], geraet: gebunden }) });
    await familie.starte();
    expect(familie.phase).toBe("wahl");
    expect(familie.waehlbar.map((p) => p.name)).toEqual(["Joris"]);
    // Ohne Bild-PIN zu wählen kostete einen Fehlversuch
    expect(f.mock.calls.some(([w]) => w === "/api/familie/wahl")).toBe(false);
  });

  it("zeigt nach der PIN der Eltern auf dem gebundenen Gerät alle, die Bindung bleibt", async () => {
    server({ "/api/familie": familieMit({ braucht_wahl: true, profile: [profil(), KIND], geraet: { gebunden_an: null, fest_auf: "k-1", offen: true } }) });
    await familie.starte();
    expect(familie.phase).toBe("wahl");
    expect(familie.waehlbar).toHaveLength(2);
    expect([familie.festAuf, familie.offen]).toEqual(["k-1", true]);
  });

  it("meldet einen Fehler des Servers, statt die Bibliothek zu zeigen", async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify({ detail: "Gerade nicht erreichbar" }), { status: 500 }))) as unknown as typeof fetch;
    await familie.starte();
    expect(familie.phase).toBe("fehler");
    expect(familie.fehler).toBe("Gerade nicht erreichbar");
  });
});

describe("Rechte an einer Stelle", () => {
  it("lässt Erwachsene sich selbst und Kinder ändern, aber keine Rollen und nichts löschen", () => {
    const selbst = profil({ id: "e-1", name: "Hanno", rolle: "erwachsen" });
    ich.setze(ichAls(selbst, ["lesen", "hinzufuegen", "freigeben"]));
    expect(ich.darfAendern(selbst)).toBe(true);
    expect(ich.darfAendern(KIND)).toBe(true);
    expect(ich.darfAendern(profil())).toBe(false);
    expect(ich.darfRolle(KIND)).toBe(false);
    expect(ich.darfLoeschen(KIND)).toBe(false);
    expect(ich.darfFreigeben(KIND)).toBe(true);
    expect(ich.mitEinstellungen).toBe(true);
    expect(ich.darf("loeschen")).toBe(false);
  });

  it("lässt die Verwaltung alles außer sich selbst löschen oder herabstufen", () => {
    const selbst = profil();
    ich.setze(ichAls(selbst, ["profile", "einstellungen", "loeschen"]));
    expect(ich.darfLoeschen(KIND)).toBe(true);
    expect(ich.darfLoeschen(selbst)).toBe(false);
    expect(ich.darfRolle(selbst)).toBe(false);
    expect(ich.darfPin(profil({ id: "e-2", rolle: "erwachsen" }))).toBe(true);
  });

  it("blendet die KI aus, wenn das Profil sie nicht hat", () => {
    anschluesse.jetzt = { ...anschluesse.jetzt, ki: true, assistent: "Assistent", bedeutung: true };
    ich.setze(ichAls(profil(), ["lesen"]));
    expect(anschluesse.jetzt.ki).toBe(false);
    expect(anschluesse.jetzt.assistent).toBe("");
    ich.setze(ichAls(profil(), ["lesen", "ki"]));
    expect(anschluesse.jetzt.ki).toBe(true);
    anschluesse.jetzt = { ...anschluesse.jetzt, ki: false, assistent: "", bedeutung: false };
  });
});

describe("Reiter der Einstellungen nach Fähigkeiten", () => {
  it("zeigt Eltern nur Familie, der Verwaltung alles", () => {
    const eltern = sichtbareReiter((f) => f === "freigeben").map(([r]) => r);
    expect(eltern).toEqual(["familie"]);
    expect(sichtbareReiter((f) => f === "einstellungen" || f === "profile")).toHaveLength(8);
    expect(reiterAus("/settings/katalog", eltern)).toEqual({ reiter: "familie", stelle: "" });
    expect(reiterAus("/settings/ai", eltern).reiter).toBe("familie");
    expect(reiterAus("/settings/familie/k-1").reiter).toBe("familie");
  });
});

describe("Freigaben eines Kindes im Zuordnen", () => {
  it("kennt das Ziel aus der Adresse und holt links die einzeln freigegebenen", async () => {
    expect(zielAus("freigabe", "k-1")?.art).toBe("freigabe");
    expect(zielAus("freigabe", "")).toBeNull();
    server({ "/api/familie/profile/k-1/freigaben": { kategorien: [], buecher: [buch(4, "Die Möwe Malu")] } });
    const liste = await freigabeziel("k-1").drinQuelle!();
    expect(liste.buecher.map((b) => b.title)).toEqual(["Die Möwe Malu"]);
    expect(liste.seiten_gesamt).toBe(1);
  });

  it("zeigt rechts nicht, was links schon steht, und nennt die Altersangabe", () => {
    const z = new Zuordnung(freigabeziel("k-1"));
    z.drin.liste = [buch(1, "Kiesel am Bach")];
    z.uebrig.liste = [buch(1, "Kiesel am Bach"), buch(2, "Nebel über dem Moor", { alter_von: 6, alter_bis: 9, alter_quelle: "Quelle B" })];
    expect(z.rechts.map((b) => b.id)).toEqual([2]);
    expect(z.ziel.merkmal?.(z.rechts[0])).toEqual({ text: "6 bis 9", titel: "Altersangabe 6 bis 9, aus Quelle B" });
  });

  it("gibt mit POST frei und nimmt mit DELETE zurück", async () => {
    const f = server({});
    const ziel = freigabeziel("k-1");
    await ziel.dazu([5, 6]);
    await ziel.heraus([5]);
    const [w1, o1] = f.mock.calls[0] as unknown as [string, RequestInit];
    const [, o2] = f.mock.calls[1] as unknown as [string, RequestInit];
    expect(w1).toBe("/api/familie/profile/k-1/freigaben");
    expect([o1.method, JSON.parse(String(o1.body))]).toEqual(["POST", { art: "buch", ziel_ids: [5, 6] }]);
    expect([o2.method, JSON.parse(String(o2.body))]).toEqual(["DELETE", { art: "buch", ziel_ids: [5] }]);
  });
});

describe("Texte des Elternbereichs", () => {
  it("schlägt die Stufe und die Lesezeit aus dem Geburtsjahr vor", () => {
    expect(stufeVorschlag(2017, STUFEN, 2026)?.name).toBe("Lesen und Lernen");
    expect(stufeVorschlag(2010, STUFEN, 2026)?.name).toBe("Jugend");
    expect(stufeVorschlag(null, STUFEN, 2026)).toBeNull();
    const vorgaben = [{ alter_von: 6, alter_bis: 8, minuten: 45, an: true }, { alter_von: 12, alter_bis: null, minuten: 90, an: false }];
    const vorgabe = lesezeitVorgabe(2019, vorgaben, 2026);
    expect(vorgabe && vorgabeText(vorgabe)).toBe("Vorgabe für 6 bis 8 Jahre: 45 Minuten");
    const gross = lesezeitVorgabe(2012, vorgaben, 2026);
    expect(gross && vorgabeText(gross)).toBe("Vorgabe ab 12 Jahren: ohne Grenze");
  });

  it("beschreibt Rolle, Stufe und PIN", () => {
    expect(rollenText(KIND, STUFEN)).toBe("Kind, Lesen und Lernen");
    expect(rollenText(profil(), STUFEN)).toBe("Verwaltung");
    expect(profilZeile(KIND)).toBe("Kind, geboren 2017, Bild-PIN gesetzt");
    expect(pinText(profil({ hat_pin: false, rolle: "erwachsen" }))).toBe("ohne PIN");
  });

  it("nennt Altersangaben mit Herkunft", () => {
    expect(alterText({ alter_von: 6, alter_bis: null })).toBe("ab 6");
    expect(alterText({ alter_von: null, alter_bis: 9 })).toBe("bis 9");
    expect(alterText({})).toBe("");
    expect(alterHinweis({ alter_von: 4, alter_bis: 7, alter_quelle: "eigen" })).toBe("Altersangabe 4 bis 7, aus eigener Angabe");
  });

  it("sagt, was die Eltern sehen und was sich mit der nächsten Stufe ändert", () => {
    expect(einblickHinweis("Joris", ["titel", "lesezeit", "fortschritt"], "lesen_lernen", STUFEN)).toBe(
      "Joris sieht im eigenen Bereich, dass du Titel, Lesezeit und Fortschritt siehst. Ab 10 Jahren nur noch Titel und grober Fortschritt.",
    );
    expect(einblickHinweis("Joris", ["titel", "grober_fortschritt"], "schule", STUFEN)).toBe(
      "Joris sieht im eigenen Bereich, dass du Titel und groben Fortschritt siehst. Ab 14 Jahren nur noch Titel und grober Fortschritt der Bücher, die Joris teilt.",
    );
    expect(einblickHinweis("Joris", ["geteiltes"], "jugend", STUFEN)).toBe("Joris sieht im eigenen Bereich, dass du nur siehst, was Joris teilt.");
    expect(einblickZeile({ buch: { id: 1, title: "x" }, fortschritt: 0.3, seite: 12, seiten: 40 })).toBe("Seite 12 von 40");
    expect(einblickZeile({ buch: { id: 1, title: "x" }, fortschritt: 0.5 })).toBe("50 Prozent");
    expect(einblickZeile({ buch: { id: 1, title: "x" }, fortschritt: null })).toBe("");
  });

  it("füllt Einstellungen aus den Vorgaben der Stufe, eigene gehen vor", () => {
    const e = einstellungenVon({ stufe: "lesen_lernen", einstellungen: { lesehilfen: { silben: false } as never } }, STUFEN);
    expect(e.lesehilfen).toEqual({ mitlesen: true, tempo: 1, silben: false, lesezeile: true, schrift: "gross", schrift_wahl: "normal", hinweise_sprechen: true, tasten_ansagen: true });
    expect(e.katze.an).toBe(false);
    // Gestaltung und Uhr im Kopf aus der Stufe (BF-88); null heißt ohne Kinderbereich und gilt als Angabe
    expect([e.gestaltung, e.uhr]).toEqual(["gross", "zeiger"]);
    expect(einstellungenVon({ stufe: "lesen_lernen", einstellungen: { gestaltung: "klein", uhr: "zahl" } }, STUFEN).gestaltung).toBe("klein");
    expect(einstellungenVon({ stufe: "jugend", einstellungen: { gestaltung: null } }, STUFEN).gestaltung).toBeNull();
    expect(tempoText(0.85)).toBe("langsam");
    expect(pinGueltig("1234", ZUGANG)).toBe(true);
    expect(pinGueltig("12a4", ZUGANG)).toBe(false);
    expect(pinGueltig("123", ZUGANG)).toBe(false);
    expect(pinGueltig("123456789", ZUGANG)).toBe(false);
  });

  it("schickt von den Einstellungen nur den geänderten Teil, so wie er wirkt", async () => {
    const f = server({ "/api/familie/profile/k-1": KIND });
    const kind = { ...KIND, einstellungen: { katze: { an: true, name: "Pünktchen", schnurren: false, name_eingabe: "tippen" as const } } };
    await setze(kind, "katze", { schnurren: true });
    const [weg, optionen] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect([weg, optionen.method]).toEqual(["/api/familie/profile/k-1", "PATCH"]);
    expect(JSON.parse(String(optionen.body))).toEqual({ einstellungen: { katze: { an: true, name: "Pünktchen", schnurren: true } } });
  });
});

describe("Bild-PIN", () => {
  it("gibt nach drei Bildern die Folge weiter und nimmt eine Stelle zurück", async () => {
    const onvoll = vi.fn();
    render(Bildpinfeld, { props: { zugang: ZUGANG, onvoll } });
    expect(screen.getAllByRole("button")).toHaveLength(ZUGANG.bilder.length);
    await fireEvent.click(screen.getByRole("button", { name: "Sonne" }));
    await fireEvent.click(screen.getByRole("button", { name: "Ball" }));
    await fireEvent.click(screen.getByRole("button", { name: "1. Bild: Sonne, zurücknehmen" }));
    expect(screen.queryByRole("button", { name: /2\. Bild/ })).toBeNull();
    for (const bild of ["Mond", "Stern", "Apfel"]) await fireEvent.click(screen.getByRole("button", { name: bild }));
    expect(onvoll).toHaveBeenCalledWith(["mond", "stern", "apfel"]);
  });
});

describe("Stimme der Ansagen", () => {
  const KLON = "0f8c2b9e-1d2a-4c3b-9e8f-7a6b5c4d3e2f";
  const FREIGABE = "Private Stimmen sind dieser App nicht erlaubt. Freigabe in der Vertonung unter Private Stimmen für";
  const KATALOG = {
    da: true, hinweis: "",
    stimmen: [{ id: KLON, name: "Probesprecher", bereich: "fremd", sprache: "de" }, { id: "katalog:serena", name: "serena", bereich: "katalog", sprache: null }],
    bereiche: [{ bereich: "privat", frei: false, hinweis: FREIGABE }, { bereich: "fremd", frei: true, hinweis: "" }, { bereich: "katalog", frei: true, hinweis: "" }],
  };
  const mitStimme = (stimme: string): Profil => ({ ...KIND, einstellungen: { lesehilfen: { mitlesen: true, tempo: 1, silben: false, lesezeile: true, schrift: "mittel", schrift_wahl: "normal", hinweise_sprechen: true, tasten_ansagen: true, stimme } } });
  const auftrag = (stand: "wartet" | "laeuft" | "fertig" | "fehler", fertig: number, grund = "") =>
    [{ was: "Ansagen erstellen", stimme: "katalog:serena", stand, gesamt: 186, fertig, grund, begonnen: null, geaendert: null, fertig_am: null }];
  const mitFamilienstimme = async (stimme: string) => {
    server({ "/api/familie": { profile: [KIND], braucht_wahl: false, aktiv: null, geraet: { gebunden_an: null, fest_auf: null, offen: false }, stimme } });
    await familie.laden();
  };

  it("zeigt die gewählte Stimme und dass die festen Ansagen bereitliegen", async () => {
    await mitFamilienstimme("");
    server({ "/api/vorlesen/stimmen": KATALOG, "/api/familie/ansagen/stand": auftrag("fertig", 186) });
    render(Ansagestimme, { props: { profil: mitStimme("katalog:serena"), aendert: true } });
    expect(await screen.findByText("186 feste Ansagen fertig, auch ohne Vertonung")).toBeTruthy();
    expect(await screen.findByRole("button", { name: "serena" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Probe" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("zeigt die Stimmen der Vertonung in Gruppen nach ihren Bereichen und den Weg zur Freigabe privater Stimmen", async () => {
    await mitFamilienstimme("");
    server({ "/api/vorlesen/stimmen": KATALOG, "/api/familie/ansagen/stand": auftrag("fertig", 186) });
    render(Ansagestimme, { props: { profil: mitStimme("katalog:serena"), aendert: true } });
    await fireEvent.click(await screen.findByRole("button", { name: "serena" }));
    const auswahl = await screen.findByRole("combobox", { name: "Stimme" });
    expect([...auswahl.querySelectorAll("optgroup")].map((g) => g.label)).toEqual(["Vorgabe", "Fremde Stimmen", "Eingebaute Stimmen", "Ohne Vertonung"]);
    expect(screen.getByText(FREIGABE)).toBeTruthy();
  });

  it("zeigt, wie weit die Ansagen entstehen, und den Grund, wenn sie nicht entstehen", async () => {
    await mitFamilienstimme("");
    server({ "/api/vorlesen/stimmen": KATALOG, "/api/familie/ansagen/stand": auftrag("laeuft", 40) });
    const { unmount } = render(Ansagestimme, { props: { profil: mitStimme("katalog:serena"), aendert: true } });
    expect(await screen.findByText(/werden erstellt: 40 von 186/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Auftrag" })).toBeTruthy();
    unmount();
    server({ "/api/vorlesen/stimmen": KATALOG, "/api/familie/ansagen/stand": auftrag("fehler", 0, "Es ist keine Vertonung angeschlossen (Anschlüsse, Vertonung)") });
    render(Ansagestimme, { props: { profil: mitStimme("katalog:serena"), aendert: true } });
    expect(await screen.findByText(/Es ist keine Vertonung angeschlossen/)).toBeTruthy();
  });

  it("folgt ohne eigene Wahl der Stimme der Familie, ohne sie bittet es um eine Wahl", async () => {
    await mitFamilienstimme("katalog:serena");
    server({ "/api/vorlesen/stimmen": KATALOG, "/api/familie/ansagen/stand": auftrag("fertig", 186) });
    const { unmount } = render(Ansagestimme, { props: { profil: mitStimme(""), aendert: true } });
    expect(screen.getByRole("button", { name: "wie die Familie" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Probe" }) as HTMLButtonElement).disabled).toBe(false);
    unmount();
    await mitFamilienstimme("");
    server({ "/api/vorlesen/stimmen": KATALOG });
    render(Ansagestimme, { props: { profil: mitStimme(""), aendert: true } });
    expect(screen.getByRole("button", { name: "Stimme wählen" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Probe" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Noch keine Stimme gewählt, die Ansagen schweigen")).toBeTruthy();
  });

  it("holt die Probe als Satz mit Adresse des Tons", async () => {
    const f = server({ "/api/familie/ansagen/probe": { text: "Hallo, ich lese dir vor.", url: "/api/familie/ansagen/ton/serena/probe-0123456789abcdef.wav" } });
    const { ansageProbe } = await import("../src/lib/api/familie");
    expect(await ansageProbe("katalog:serena")).toEqual({ text: "Hallo, ich lese dir vor.", url: "/api/familie/ansagen/ton/serena/probe-0123456789abcdef.wav" });
    const [, optionen] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(optionen.body))).toEqual({ stimme: "katalog:serena" });
  });
});

describe("Fertig gelesen", () => {
  it("markiert fertig gelesen, der Zeitpunkt des letzten Lesens bleibt", async () => {
    server({ "/api/books/3/gelesen": { book_id: 3, gelesen: true } });
    const { merkmale } = await import("../src/lib/stand/merkmale.svelte");
    const vorher = buch(3, "Die Möwe Malu", { last_read_at: "2026-11-20 10:00:00", fertig_am: null });
    const neu = await merkmale.gelesen(vorher);
    expect(neu.fertig_am).toBeTruthy();
    expect(neu.last_read_at).toBe("2026-11-20 10:00:00");
    server({ "/api/books/3/gelesen": { book_id: 3, gelesen: false } });
    expect(await merkmale.gelesen({ ...vorher, fertig_am: "2026-11-21 10:00:00" })).toEqual({ fertig_am: null });
  });
});
