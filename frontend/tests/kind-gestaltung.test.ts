// Zwei Gestaltungen des Kinderbereichs (BF-88): Klein und Groß nach der Stufe, je Kind umstellbar; die Uhr im Kopf, die
// Leseschrift, die das Kind in Groß selbst schaltet, Weiterlesen und die Wahl im Elternbereich. Nur erfundene Namen und Titel.
import { fireEvent, render, screen } from "@testing-library/svelte";
import type { Profil, Stufenangabe } from "../src/lib/api/familie";
import { ichAus, katzeAus, nutztKinderbereich } from "../src/lib/kind/ich";
import { TASTE } from "../src/lib/kind/ansagen";
import { FERTIG_AB, weiterzulesen } from "../src/lib/kind/stelle";
import { lesetasten, tastenansage, tastenbild, type Tastenstand } from "../src/lib/kind/tasten";
import { faehigkeitenAus, darstellungAus } from "../src/lib/kind/ich";
import { familie } from "../src/lib/stand/familie.svelte";
import { ich } from "../src/lib/stand/ich.svelte";
import Stufenfeld from "../src/ansichten/einstellungen/familie/Stufenfeld.svelte";
import Lesezeitfeld from "../src/ansichten/einstellungen/familie/Lesezeitfeld.svelte";
import Lesehilfenfeld from "../src/ansichten/einstellungen/familie/Lesehilfenfeld.svelte";
import type { Buch } from "../src/lib/typen";

const stand = (teil: Partial<Tastenstand> = {}): Tastenstand => ({ vorlesen: "aus", silben: false, zeile: false, kinderschrift: false, stift: false, gemerkt: false, ...teil });

describe("Gestaltung aus GET /api/familie/ich", () => {
  it("nimmt, was der Server sagt, und ohne Angabe die Stufe", () => {
    expect(ichAus({ profil: { rolle: "kind", stufe: "vorlesen" } }).gestaltung).toBe("klein");
    expect(ichAus({ profil: { rolle: "kind", stufe: "lesen_lernen" } }).gestaltung).toBe("gross");
    expect(ichAus({ profil: { rolle: "kind", stufe: "vorlesen" }, gestaltung: "gross", uhr: "zahl" })).toMatchObject({ gestaltung: "gross", uhr: "zahl" });
    expect(ichAus({ profil: { rolle: "kind", stufe: "schule" } }).uhr).toBe("zahl");
    expect(ichAus({ profil: { rolle: "kind", stufe: "lesen_lernen" }, uhr: "sanduhr" }).uhr).toBe("zeiger");
    expect(ichAus({ profil: { rolle: "kind", stufe: "jugend" } }).gestaltung).toBeNull();
    expect(ichAus({ profil: { rolle: "erwachsen" }, gestaltung: "gross" }).gestaltung).toBeNull();
  });

  it("den Kinderbereich nutzt nur ein Kind mit Gestaltung", () => {
    expect(nutztKinderbereich({ profil: { rolle: "kind", stufe: "schule" }, gestaltung: "gross" })).toBe(true);
    expect(nutztKinderbereich({ profil: { rolle: "kind", stufe: "schule" }, gestaltung: null })).toBe(false);
    expect(nutztKinderbereich({ profil: { rolle: "kind", stufe: "jugend" } })).toBe(false);
    expect(nutztKinderbereich({ profil: { rolle: "erwachsen", stufe: null }, gestaltung: "klein" })).toBe(false);
  });

  it("die Katze ist in Groß anfangs aus, in Klein an", () => {
    expect(katzeAus({}, "erstes_lesen").an).toBe(true);
    expect(katzeAus({}, "lesen_lernen").an).toBe(false);
    expect(katzeAus({ an: true }, "schule").an).toBe(true);
  });

  it("liest die Leseschrift: normal in Groß, Kinderschrift in Klein, die Wahl geht vor", () => {
    expect(darstellungAus({}, "schule").schrift_wahl).toBe("normal");
    expect(darstellungAus({}, "schule").schrift).toContain("Atkinson");
    expect(darstellungAus({}, "erstes_lesen").schrift_wahl).toBe("kinderschrift");
    const lena = ichAus({ profil: { rolle: "kind", stufe: "lesen_lernen" }, darstellung: { schrift: "kinderschrift", buchstabe: 0.12 }, lesehilfen: { schrift_wahl: "kinderschrift" } });
    expect(lena.darstellung.schrift_wahl).toBe("kinderschrift");
    expect(lena.darstellung.schrift).toContain("Andika");
    expect(lena.darstellung.abstand_buchstabe).toBe(0.12);
  });
});

describe("Tasten in Groß", () => {
  it("dazu die Schrift, die das Kind selbst schaltet, nach den Lesehilfen", () => {
    const lena = lesetasten(faehigkeitenAus(undefined, "lesen_lernen"), darstellungAus({}, "lesen_lernen", { silben: true }), true, true);
    expect(lena).toEqual(["zurueck", "vorlesen", "silben", "zeile", "schrift", "weiter"]);
    const noah = lesetasten(faehigkeitenAus(undefined, "schule"), darstellungAus({}, "schule"), true, true);
    expect(noah).toEqual(["zurueck", "merken", "vorlesen", "schrift", "stift", "notiz", "weiter"]);
    expect(lesetasten(faehigkeitenAus(undefined, "schule"), darstellungAus({}, "schule"), true)).not.toContain("schrift");
  });

  it("die Schrift leuchtet mit der Kinderschrift und sagt, wie sie steht", () => {
    expect(tastenbild("schrift", stand({ kinderschrift: true }))).toMatchObject({ name: "Schrift", symbol: "font", an: true });
    expect(tastenbild("schrift", stand()).an).toBe(false);
    expect(tastenansage("schrift", stand({ kinderschrift: true }))).toBe(TASTE.kinderschriftAn);
    expect(tastenansage("schrift", stand())).toBe(TASTE.kinderschriftAus);
    expect([TASTE.kinderschriftAn, TASTE.kinderschriftAus]).toEqual(["tasten.kinderschrift_an", "tasten.kinderschrift_aus"]);
  });
});

describe("Weiterlesen", () => {
  const buch = (id: number, reading_position: string, last_read_at: string | null, page_count = 40) =>
    ({ id, title: `Probebuch ${id}`, reading_position, last_read_at, page_count }) as unknown as Buch;

  it("nimmt das zuletzt gelesene Buch, das noch nicht zu Ende ist", () => {
    const liste = [
      buch(1, "page:12", "2026-11-20T10:00:00"),
      buch(2, "page:5", "2026-11-25T10:00:00"),
      buch(3, `page:${Math.ceil(40 * FERTIG_AB)}`, "2026-11-26T10:00:00"),
      buch(4, "", null),
    ];
    expect(weiterzulesen(liste)?.id).toBe(2);
    expect(weiterzulesen([buch(4, "", null)])).toBeNull();
    expect(weiterzulesen([])).toBeNull();
  });
});

describe("Gestaltung im Elternbereich", () => {
  const STUFEN: Stufenangabe[] = [
    { schluessel: "erstes_lesen", name: "Erstes Lesen", alter_von: 6, alter_bis: 7, faehigkeiten: ["lesen"], einblick: ["titel"],
      vorgaben: { gestaltung: "klein", uhr: "zeiger", lesehilfen: { mitlesen: true, tempo: 1, silben: false, lesezeile: true, schrift: "mittel", schrift_wahl: "kinderschrift", hinweise_sprechen: true, tasten_ansagen: true } } },
    { schluessel: "schule", name: "Schule", alter_von: 10, alter_bis: 13, faehigkeiten: ["lesen"], einblick: ["titel"],
      vorgaben: { gestaltung: "gross", uhr: "zahl", lesehilfen: { mitlesen: false, tempo: 1, silben: false, lesezeile: false, schrift: "mittel", schrift_wahl: "normal", hinweise_sprechen: false, tasten_ansagen: false } } },
    { schluessel: "jugend", name: "Jugend", alter_von: 14, alter_bis: null, faehigkeiten: ["lesen"], einblick: ["titel"],
      vorgaben: { gestaltung: null, uhr: "zahl", lesehilfen: { mitlesen: false, tempo: 1, silben: false, lesezeile: false, schrift: "mittel", schrift_wahl: "normal", hinweise_sprechen: false, tasten_ansagen: false } } },
  ];
  const kind = (stufe: Profil["stufe"], einstellungen: Profil["einstellungen"] = null): Profil =>
    ({ id: "k-2", name: "Juna", zeichen: "rocket", farbe: "#b5476a", rolle: "kind", stufe, hat_pin: false, hat_bild_pin: false, geburtsjahr: 2015, einstellungen });

  function server() {
    const f = vi.fn((weg: string, _init?: RequestInit) => {
      const pfad = weg.split("?")[0];
      if (pfad === "/api/familie/stufen") return Promise.resolve(new Response(JSON.stringify({ stufen: STUFEN, lesezeit: [], zugang: { pin_stellen_von: 4, pin_stellen_bis: 8, bild_pin_anzahl: 3, bilder: [] } })));
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    globalThis.fetch = f as unknown as typeof fetch;
    return f;
  }
  const gesendet = (f: ReturnType<typeof server>) =>
    f.mock.calls.filter(([, init]) => init?.method === "PATCH").map(([weg, init]) => [weg, JSON.parse(String(init?.body))]);

  beforeEach(async () => {
    server();
    await familie.ladeStufen();
  });
  afterEach(() => ich.setze(null));

  it("stellt die Gestaltung je Kind um und nennt die Vorgabe der Stufe", async () => {
    const f = server();
    await familie.ladeStufen();
    render(Stufenfeld, { props: { profil: kind("schule"), aendert: true } });
    expect(screen.getByText("Vorgabe aus der Stufe: Groß")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Groß" }).getAttribute("aria-pressed")).toBe("true");
    await fireEvent.click(screen.getByRole("button", { name: "Klein" }));
    expect(gesendet(f)).toEqual([["/api/familie/profile/k-2", { einstellungen: { gestaltung: "klein" } }]]);
  });

  it("zeigt für Jugend keine Gestaltung", async () => {
    render(Stufenfeld, { props: { profil: kind("jugend"), aendert: true } });
    expect(screen.queryByRole("group", { name: "Gestaltung" })).toBeNull();
  });

  it("die Uhr im Kopf gilt nur in Groß, in Klein ist sie gesperrt", async () => {
    const f = server();
    await familie.ladeStufen();
    const { unmount } = render(Lesezeitfeld, { props: { profil: kind("erstes_lesen"), aendert: true } });
    expect((screen.getByRole("button", { name: "Zahl" }) as HTMLButtonElement).disabled).toBe(true);
    unmount();
    render(Lesezeitfeld, { props: { profil: kind("schule"), aendert: true } });
    expect(screen.getByRole("button", { name: "Zahl" }).getAttribute("aria-pressed")).toBe("true");
    await fireEvent.click(screen.getByRole("button", { name: "Zeiger" }));
    expect(gesendet(f)).toEqual([["/api/familie/profile/k-2", { einstellungen: { uhr: "zeiger" } }]]);
  });

  it("gibt die Schrift vor: normal oder Kinderschrift, und sperrt die Stimme, solange nichts angesagt wird", async () => {
    const f = server();
    await familie.ladeStufen();
    render(Lesehilfenfeld, { props: { profil: kind("schule"), aendert: true } });
    expect(screen.getByText("Vorgabe in Groß: Normal")).toBeTruthy();
    expect(screen.getByText("wirkt, sobald Hinweise oder Tasten an sind")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Probe" }) as HTMLButtonElement).disabled).toBe(true);
    await fireEvent.click(screen.getByRole("button", { name: "Kinderschrift" }));
    const [[weg, body]] = gesendet(f);
    expect(weg).toBe("/api/familie/profile/k-2");
    expect(body.einstellungen.lesehilfen.schrift_wahl).toBe("kinderschrift");
  });
});
