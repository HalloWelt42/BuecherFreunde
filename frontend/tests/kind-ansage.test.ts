// Ansagen im Kinderbereich (BF-78, Entwurf Runde 4): welche Taste was sagt, Abbrechen, nie über dem Vorlesen, Rückfall auf die
// Stimme des Geräts, und welche Tasten es je Stufe gibt
import { Ansage, type Ansageton, type Tonquelle } from "../src/lib/kind/ansage.svelte";
import { faehigkeitenAus, darstellungAus } from "../src/lib/kind/ich";
import { lesetasten, steuertVorlesen, tastenansage, tastenbild, type Tastenstand } from "../src/lib/kind/tasten";

class Probeton implements Tonquelle {
  geholt: string[] = [];
  gespielt: string[] = [];
  gesprochen: string[] = [];
  abgebrochen: string[] = [];
  antwort: (text: string) => Ansageton = () => new Blob(["ton"]);
  entsperrt = 0;
  #ende: (() => void)[] = [];

  async hole(text: string): Promise<Ansageton> {
    this.geholt.push(text);
    return this.antwort(text);
  }
  #warte(text: string, liste: string[], abbruch: AbortSignal): Promise<void> {
    liste.push(text);
    return new Promise<void>((fertig) => {
      abbruch.addEventListener("abort", () => {
        this.abgebrochen.push(text);
        fertig();
      });
      this.#ende.push(fertig);
    });
  }
  spiele(_ton: Blob, abbruch: AbortSignal): Promise<void> {
    return this.#warte(`Ton ${this.geholt.at(-1)}`, this.gespielt, abbruch);
  }
  sprich(text: string, abbruch: AbortSignal): Promise<void> {
    return this.#warte(text, this.gesprochen, abbruch);
  }
  entsperre(): void {
    this.entsperrt++;
  }
  /** Die laufende Ansage endet von selbst */
  ende(): void {
    this.#ende.shift()?.();
  }
}

const ruhe = () => new Promise((r) => setTimeout(r, 0));

function ansage(klingt = false) {
  const ton = new Probeton();
  let vorlesen = klingt;
  const a = new Ansage(ton, () => vorlesen);
  a.stelle(true, true);
  return { a, ton, vorlesen: (an: boolean) => (vorlesen = an) };
}

const stand = (teil: Partial<Tastenstand> = {}): Tastenstand => ({ vorlesen: "aus", silben: false, zeile: false, stift: false, gemerkt: false, ...teil });

describe("Tasten", () => {
  it("sagen nach dem Druck ihren Namen und bei Schaltern, wie sie nun stehen", () => {
    expect(tastenansage("weiter", stand())).toBe("Weiter");
    expect(tastenansage("zurueck", stand())).toBe("Zurück");
    expect(tastenansage("silben", stand({ silben: true }))).toBe("Silben an");
    expect(tastenansage("zeile", stand({ zeile: false }))).toBe("Zeile aus");
    expect(tastenansage("merken", stand({ gemerkt: true }))).toBe("Gemerkt");
    expect(tastenansage("notiz", stand())).toBe("Notiz");
  });

  it("sagen beim Vorlesen, was jetzt geschieht", () => {
    expect(tastenansage("vorlesen", stand({ vorlesen: "laeuft" }), "aus")).toBe("Vorlesen");
    expect(tastenansage("vorlesen", stand({ vorlesen: "ruht" }), "laeuft")).toBe("Pause");
    expect(tastenansage("vorlesen", stand({ vorlesen: "laeuft" }), "ruht")).toBe("Weiter");
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

  it("sprechen bis Lesen und Lernen von selbst, ab Schule nicht", () => {
    expect(darstellungAus({}, "lesen_lernen").tasten_ansagen).toBe(true);
    expect(darstellungAus({}, "erstes_lesen").hinweise_sprechen).toBe(true);
    expect(darstellungAus({}, "schule").tasten_ansagen).toBe(false);
    expect(darstellungAus({}, "schule", { hinweise_sprechen: true }).hinweise_sprechen).toBe(true);
  });
});

describe("Ansage", () => {
  it("bleibt vor dem ersten Antippen still", async () => {
    const { a, ton } = ansage();
    await a.taste("Weiter");
    expect(ton.geholt).toEqual([]);
    a.freigeben();
    expect(ton.entsperrt).toBe(1);
    void a.taste("Weiter");
    await ruhe();
    expect(ton.gespielt).toEqual(["Ton Weiter"]);
  });

  it("beendet eine laufende Ansage mit der neuen, ohne Warteschlange", async () => {
    const { a, ton } = ansage();
    a.freigeben();
    void a.taste("Weiter");
    await ruhe();
    void a.taste("Zurück");
    await ruhe();
    expect(ton.abgebrochen).toEqual(["Ton Weiter"]);
    expect(ton.gespielt).toEqual(["Ton Weiter", "Ton Zurück"]);
    ton.ende();
    await ruhe();
    expect(ton.gespielt).toHaveLength(2);
  });

  it("spricht nie über dem Vorlesen; nur Tasten, die es steuern, sagen kurz an", async () => {
    const { a, ton } = ansage(true);
    a.freigeben();
    await a.hinweis("Gleich ist die Lesezeit um.");
    await a.taste("Silben an");
    expect(ton.geholt).toEqual([]);
    void a.taste("Pause", true);
    await ruhe();
    expect(ton.gespielt).toEqual(["Ton Pause"]);
  });

  it("lässt das Vorlesen erst nach der Ansage weiterklingen", async () => {
    const { a, ton } = ansage();
    a.freigeben();
    void a.taste("Weiter", true);
    let weiter = false;
    void a.fertig().then(() => (weiter = true));
    await ruhe();
    expect(weiter).toBe(false);
    ton.ende();
    await ruhe();
    expect(weiter).toBe(true);
  });

  it("spricht mit der Stimme des Geräts, wenn der Weg fehlt, und fragt dann nicht mehr", async () => {
    const { a, ton } = ansage();
    ton.antwort = () => "fehlt";
    a.freigeben();
    void a.hinweis("Frag Mama oder Papa.");
    await ruhe();
    expect(ton.gesprochen).toEqual(["Frag Mama oder Papa."]);
    void a.hinweis("Jetzt ruhen die Bücher.");
    await ruhe();
    expect(ton.geholt).toEqual(["Frag Mama oder Papa."]);
    expect(ton.gesprochen).toEqual(["Frag Mama oder Papa.", "Jetzt ruhen die Bücher."]);
  });

  it("nimmt bei einem nicht bereiten Sprechdienst diesmal das Gerät und fragt beim nächsten Mal wieder", async () => {
    const { a, ton } = ansage();
    ton.antwort = (t) => (t === "Weiter" ? "spaeter" : new Blob(["ton"]));
    a.freigeben();
    void a.taste("Weiter");
    await ruhe();
    void a.taste("Zurück");
    await ruhe();
    expect(ton.gesprochen).toEqual(["Weiter"]);
    expect(ton.gespielt).toEqual(["Ton Zurück"]);
  });

  it("merkt sich den Ton fester Sätze und holt ihn nur einmal", async () => {
    const { a, ton } = ansage();
    a.freigeben();
    for (let i = 0; i < 3; i++) {
      void a.taste("Weiter");
      await ruhe();
    }
    expect(ton.geholt).toEqual(["Weiter"]);
    expect(ton.gespielt).toHaveLength(3);
  });

  it("schweigt, wenn die Eltern es ausschalten", async () => {
    const { a, ton } = ansage();
    a.freigeben();
    a.stelle(false, true);
    await a.hinweis("Frag Mama oder Papa.");
    void a.taste("Weiter");
    await ruhe();
    a.stelle(true, false);
    await a.taste("Zurück");
    expect(ton.geholt).toEqual(["Weiter"]);
  });
});
