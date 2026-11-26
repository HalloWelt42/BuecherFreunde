// Ansagen im Kinderbereich (BF-78, Entwurf Runde 4): welche Taste was sagt, fertige Töne nach Schlüssel ohne Pause
// hintereinander, Abbrechen, nie über dem Vorlesen, still bei fehlendem Ton, die Stimme des Geräts nur auf Wunsch der Eltern,
// und welche Tasten es je Stufe gibt
import { Ansage, GERAETESTIMME, type Ansagekatalog, type Tonquelle } from "../src/lib/kind/ansage.svelte";
import { HINWEIS, TASTE, uhrfolge } from "../src/lib/kind/ansagen";
import { faehigkeitenAus, darstellungAus } from "../src/lib/kind/ich";
import { lesetasten, steuertVorlesen, tastenansage, tastenbild, type Tastenstand } from "../src/lib/kind/tasten";

/** Ein Katalog, in dem jeder genannte Schlüssel einen Ton hat */
function katalog(schluessel: string[], teil: Partial<Ansagekatalog> = {}): Ansagekatalog {
  return { stimme: "probe", fertig: schluessel.length, gesamt: schluessel.length, laeuft: false, eintraege: Object.fromEntries(schluessel.map((s) => [s, { text: `Text ${s}`, url: `/ton/${s}` }])), ...teil };
}

class Probeton implements Tonquelle {
  geholt: string[] = [];
  gespielt: string[] = [];
  gesprochen: string[] = [];
  abgebrochen: string[] = [];
  entsperrt = 0;
  liste: Ansagekatalog = katalog([]);
  #ende: (() => void)[] = [];

  async katalog(): Promise<Ansagekatalog> {
    return this.liste;
  }
  async hole(url: string): Promise<Blob> {
    this.geholt.push(url);
    return new Blob([url]);
  }
  #warte(was: string, liste: string[], abbruch: AbortSignal): Promise<void> {
    liste.push(was);
    return new Promise<void>((fertig) => {
      abbruch.addEventListener("abort", () => {
        this.abgebrochen.push(was);
        fertig();
      });
      this.#ende.push(fertig);
    });
  }
  async spiele(ton: Blob, abbruch: AbortSignal): Promise<void> {
    return this.#warte(await ton.text(), this.gespielt, abbruch);
  }
  sprich(text: string, abbruch: AbortSignal): Promise<void> {
    return this.#warte(text, this.gesprochen, abbruch);
  }
  entsperre(): void {
    this.entsperrt++;
  }
  /** Der laufende Ton endet von selbst */
  ende(): void {
    this.#ende.shift()?.();
  }
}

const ruhe = () => new Promise((r) => setTimeout(r, 0));

async function ansage(schluessel: string[], teil: Partial<Ansagekatalog> = {}, klingt = false) {
  const ton = new Probeton();
  ton.liste = katalog(schluessel, teil);
  const a = new Ansage(ton, () => klingt);
  a.stelle(true, true);
  await a.lade();
  a.beende();
  a.freigeben();
  return { a, ton };
}

const stand = (teil: Partial<Tastenstand> = {}): Tastenstand => ({ vorlesen: "aus", silben: false, zeile: false, kinderschrift: false, stift: false, gemerkt: false, ...teil });

describe("Tasten", () => {
  it("sagen nach dem Druck ihren Namen und bei Schaltern, wie sie nun stehen", () => {
    expect(tastenansage("weiter", stand())).toBe(TASTE.weiter);
    expect(tastenansage("zurueck", stand())).toBe(TASTE.zurueck);
    expect(tastenansage("silben", stand({ silben: true }))).toBe(TASTE.silbenAn);
    expect(tastenansage("zeile", stand({ zeile: false }))).toBe(TASTE.zeileAus);
    expect(tastenansage("merken", stand({ gemerkt: true }))).toBe(TASTE.gemerkt);
    expect(tastenansage("notiz", stand())).toBe(TASTE.notiz);
  });

  it("sagen beim Vorlesen, was jetzt geschieht", () => {
    expect(tastenansage("vorlesen", stand({ vorlesen: "laeuft" }), "aus")).toBe(TASTE.vorlesen);
    expect(tastenansage("vorlesen", stand({ vorlesen: "ruht" }), "laeuft")).toBe(TASTE.pause);
    expect(tastenansage("vorlesen", stand({ vorlesen: "laeuft" }), "ruht")).toBe(TASTE.weiterHoeren);
    expect(tastenbild("vorlesen", stand({ vorlesen: "laeuft" })).name).toBe("Pause");
    expect(tastenbild("vorlesen", stand({ vorlesen: "ruht" })).name).toBe("Weiter hören");
    expect(steuertVorlesen("vorlesen") && steuertVorlesen("weiter") && !steuertVorlesen("silben")).toBe(true);
  });

  it("gibt es nur, wenn die Stufe sie erlaubt: für kleine Kinder kein Merken, keine Notizen, kein Stift", () => {
    // Lesen und Lernen mit den Silben, die die Eltern erlauben: fünf Tasten wie im Entwurf
    const klein = lesetasten(faehigkeitenAus(["lesen", "vorlesen", "favoriten"], "lesen_lernen"), darstellungAus({}, "lesen_lernen", { silben: true }), true);
    expect(klein).toEqual(["zurueck", "vorlesen", "silben", "zeile", "weiter"]);
    expect(lesetasten(faehigkeitenAus(undefined, "lesen_lernen"), darstellungAus({}, "lesen_lernen"), true)).toEqual(["zurueck", "vorlesen", "zeile", "weiter"]);
    expect(lesetasten(faehigkeitenAus(undefined, "vorlesen"), darstellungAus({}, "vorlesen"), true)).toEqual(["zurueck", "vorlesen", "weiter"]);
    const schule = lesetasten(faehigkeitenAus(undefined, "schule"), darstellungAus({}, "schule"), true);
    expect(schule).toEqual(["zurueck", "merken", "vorlesen", "stift", "notiz", "weiter"]);
    expect(lesetasten(faehigkeitenAus(["lesen", "vorlesen"], "schule"), darstellungAus({ silben: false, lesezeile: false }, "schule"), false)).toEqual(["zurueck", "weiter"]);
  });

  it("sprechen in Klein von selbst, in Groß (ab Lesen und Lernen) anfangs nicht", () => {
    expect(darstellungAus({}, "lesen_lernen").tasten_ansagen).toBe(false);
    expect(darstellungAus({}, "erstes_lesen").hinweise_sprechen).toBe(true);
    expect(darstellungAus({}, "schule").tasten_ansagen).toBe(false);
    expect(darstellungAus({}, "schule", { hinweise_sprechen: true }).hinweise_sprechen).toBe(true);
  });

  it("setzen die Uhr aus Bausteinen zusammen", () => {
    expect(uhrfolge(16, 35, 25)).toEqual(["uhr.4", "minute.35", "noch.25"]);
    expect(uhrfolge(12, 0, 200)).toEqual(["uhr.12", "noch.120"]);
    expect(uhrfolge(7, 5, null)).toEqual(["uhr.7", "minute.5"]);
    // Tasten und Hinweise wie in backend/app/familie/ansagen.json
    expect([TASTE.weiter, TASTE.schloss, HINWEIS.fragEltern, HINWEIS.lesezeitBald]).toEqual(["tasten.weiter", "tasten.schloss", "hinweise.frag_eltern", "hinweise.lesezeit_gleich_um"]);
  });
});

describe("Ansage", () => {
  it("bleibt vor dem ersten Antippen still", async () => {
    const ton = new Probeton();
    ton.liste = katalog([TASTE.weiter]);
    const a = new Ansage(ton, () => false);
    a.stelle(true, true);
    await a.lade();
    a.beende();
    await a.taste([TASTE.weiter]);
    expect(ton.geholt).toEqual([]);
    a.freigeben();
    expect(ton.entsperrt).toBe(1);
    void a.taste([TASTE.weiter]);
    await ruhe();
    expect(ton.gespielt).toEqual(["/ton/tasten.weiter"]);
  });

  it("spielt eine Folge fertiger Töne ohne Pause hintereinander", async () => {
    const folge = uhrfolge(16, 35, 25);
    const { a, ton } = await ansage(folge);
    void a.hinweis(folge);
    await ruhe();
    // Alle Töne sind vorher geholt, damit keine Lücke entsteht
    expect(ton.geholt).toEqual(folge.map((s) => `/ton/${s}`));
    expect(ton.gespielt).toEqual(["/ton/uhr.4"]);
    ton.ende();
    await ruhe();
    ton.ende();
    await ruhe();
    expect(ton.gespielt).toEqual(folge.map((s) => `/ton/${s}`));
  });

  it("beendet eine laufende Ansage mit der neuen, ohne Warteschlange", async () => {
    const { a, ton } = await ansage([TASTE.weiter, TASTE.zurueck]);
    void a.taste([TASTE.weiter]);
    await ruhe();
    void a.taste([TASTE.zurueck]);
    await ruhe();
    expect(ton.abgebrochen).toEqual(["/ton/tasten.weiter"]);
    expect(ton.gespielt).toEqual(["/ton/tasten.weiter", "/ton/tasten.zurueck"]);
  });

  it("spricht nie über dem Vorlesen; nur Tasten, die es steuern, sagen kurz an", async () => {
    const { a, ton } = await ansage([HINWEIS.lesezeitBald, TASTE.silbenAn, TASTE.pause], {}, true);
    await a.hinweis([HINWEIS.lesezeitBald]);
    await a.taste([TASTE.silbenAn]);
    expect(ton.geholt).toEqual([]);
    void a.taste([TASTE.pause], true);
    await ruhe();
    expect(ton.gespielt).toEqual(["/ton/tasten.pause"]);
  });

  it("lässt das Vorlesen erst nach der Ansage weiterklingen", async () => {
    const { a, ton } = await ansage([TASTE.weiterHoeren]);
    void a.taste([TASTE.weiterHoeren], true);
    let weiter = false;
    void a.fertig().then(() => (weiter = true));
    await ruhe();
    expect(weiter).toBe(false);
    ton.ende();
    await ruhe();
    expect(weiter).toBe(true);
  });

  it("bleibt still, wenn ein Ton fehlt oder noch entsteht, ohne auf die Stimme des Geräts auszuweichen", async () => {
    const { a, ton } = await ansage(["uhr.4"], { laeuft: true });
    ton.liste.eintraege["minute.35"] = { text: "fünfunddreißig", url: "" };
    await a.hinweis(["uhr.4", "minute.35"]);
    await a.hinweis([HINWEIS.fragEltern]);
    expect(ton.geholt).toEqual([]);
    expect(ton.gesprochen).toEqual([]);
  });

  it("spricht mit der Stimme des Geräts nur, wenn die Eltern sie gewählt haben", async () => {
    const folge = uhrfolge(9, 0, 5);
    const { a, ton } = await ansage(folge, { stimme: GERAETESTIMME });
    void a.hinweis(folge);
    await ruhe();
    expect(ton.geholt).toEqual([]);
    expect(ton.gesprochen).toEqual(["Text uhr.9 Text noch.5"]);
  });

  it("holt jeden Ton nur einmal und merkt ihn sich", async () => {
    const { a, ton } = await ansage([TASTE.weiter]);
    for (let i = 0; i < 3; i++) {
      void a.taste([TASTE.weiter]);
      await ruhe();
    }
    expect(ton.geholt).toEqual(["/ton/tasten.weiter"]);
    expect(ton.gespielt).toHaveLength(3);
  });

  it("fragt nach, solange die Töne noch entstehen", async () => {
    vi.useFakeTimers();
    const ton = new Probeton();
    ton.liste = katalog([], { laeuft: true });
    const holen = vi.spyOn(ton, "katalog");
    const a = new Ansage(ton, () => false);
    await a.lade();
    expect(holen).toHaveBeenCalledTimes(1);
    ton.liste = katalog([TASTE.weiter]);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(holen).toHaveBeenCalledTimes(2);
    expect(a.katalog?.laeuft).toBe(false);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(holen).toHaveBeenCalledTimes(2);
    a.beende();
    vi.useRealTimers();
  });

  it("schweigt, wenn die Eltern es ausschalten", async () => {
    const { a, ton } = await ansage([HINWEIS.fragEltern, TASTE.weiter, TASTE.zurueck]);
    a.stelle(false, true);
    await a.hinweis([HINWEIS.fragEltern]);
    void a.taste([TASTE.weiter]);
    await ruhe();
    a.stelle(true, false);
    await a.taste([TASTE.zurueck]);
    expect(ton.geholt).toEqual(["/ton/tasten.weiter"]);
  });
});
