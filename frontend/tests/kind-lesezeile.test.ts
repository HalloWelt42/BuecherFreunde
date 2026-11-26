// Kinderleser (BF-78): kurze Zeilen nach Sinnschritten, Seiten ohne Rollen, Lesezeile, Blättern, Lesezeichen, Mitlesen und
// das Ende der Seite, wenn die Ruhe fällig ist. Text erfunden.
import { einheitAus, einheitAusText, lageVon, type Kinderquelle } from "../src/lib/kind/inhalt";
import { Kinderlesestand, type Lesergriffe } from "../src/lib/kind/leser.svelte";
import { geschaetztesWort, wortBei } from "../src/lib/kind/mitlesen";
import { seiteBei, seitenAus, type Seitenmass } from "../src/lib/kind/seiten";
import { woerterAus, zeilenAus, zeilenende } from "../src/lib/kind/umbruch";
import type { Einheit, Wort } from "../src/lib/kind/typen";

const ruhe = (n = 8) => new Array(n).fill(0).reduce((p) => p.then(() => new Promise((r) => setTimeout(r, 0))), Promise.resolve());

/** Jedes Zeichen 10 Pixel breit */
const mass = (t: string) => t.length * 10;
const text = (z: Wort[][]) => z.map((zeile) => zeile.map((w) => w.text).join(" "));

function seitenmass(teil: Partial<Seitenmass> = {}): Seitenmass {
  return { text: { breite: 400, hoehe: 200 }, textMitBild: { breite: 200, hoehe: 200 }, zeile: 40, titelzeile: 50, absatz: 20, woerter: 5, leer: 10, mass, titelmass: mass, ...teil };
}

describe("Zeilen", () => {
  it("nimmt höchstens so viele Wörter, wie die Stufe sagt", () => {
    const w = woerterAus("eins zwei drei vier fünf sechs sieben");
    expect(text(zeilenAus(w, { woerter: 4, breite: 10_000, leer: 10 }, mass))).toEqual(["eins zwei drei vier", "fünf sechs sieben"]);
  });

  it("bricht nie breiter als die Fläche um und nimmt immer mindestens ein Wort", () => {
    const w = woerterAus("Ein Schmetterlingsflügel glänzt");
    expect(text(zeilenAus(w, { woerter: 0, breite: 120, leer: 10 }, mass))).toEqual(["Ein", "Schmetterlingsflügel", "glänzt"]);
  });

  it("bricht am Anfang nach einem Sinnschritt um, wenn die Zeile halb voll bleibt", () => {
    const w = woerterAus("Der Hund bellt, dann rennt er los.");
    expect(text(zeilenAus(w, { woerter: 5, breite: 10_000, leer: 10 }, mass))).toEqual(["Der Hund bellt,", "dann rennt er los."]);
    const b = woerterAus("Sie lacht laut und springt hoch");
    expect(text(zeilenAus(b, { woerter: 5, breite: 10_000, leer: 10 }, mass))).toEqual(["Sie lacht laut", "und springt hoch"]);
  });

  it("bricht ohne Wortgrenze der Stufe nur nach Breite um", () => {
    const w = woerterAus("Der Hund bellt, dann rennt er los.");
    expect(zeilenende(w, 0, { woerter: 0, breite: 10_000, leer: 10 }, mass)).toBe(w.length);
  });
});

describe("Seiten", () => {
  const einheit = einheitAus(0, [
    { art: "titel", text: "Am Teich" },
    { art: "absatz", text: "eins zwei drei vier fünf sechs sieben acht" },
    { art: "bild", bild: { adresse: "blob:bild", verhaeltnis: 1, text: "" } },
    { art: "absatz", text: "neun zehn elf zwölf" },
  ]);

  it("legt den Text der Einheit wie beim Vorlesen an", () => {
    expect(einheit.text).toBe("Am Teich\n\neins zwei drei vier fünf sechs sieben acht\n\nneun zehn elf zwölf");
    const w = einheit.bloecke[1];
    expect(w.art === "absatz" && einheit.text.slice(w.woerter[2].von, w.woerter[2].bis)).toBe("drei");
  });

  it("füllt Seiten nach Höhe, beginnt mit einem Bild eine neue Seite und hält Lagen", () => {
    const seiten = seitenAus(0, einheit.bloecke, seitenmass());
    expect(seiten.map((s) => [s.bild ? "Bild" : "", ...text(s.zeilen.map((z) => z.woerter))])).toEqual([
      ["", "Am Teich", "eins zwei drei vier fünf", "sechs sieben acht"],
      ["Bild", "neun zehn elf zwölf"],
    ]);
    expect(seiten[1].von).toBe(einheit.text.indexOf("neun") - 2);
    expect(seiteBei(seiten, einheit.text.indexOf("elf"))).toBe(1);
    expect(seiteBei(seiten, 0)).toBe(0);
  });

  it("stellt ein Bild direkt nach einer Überschrift mit ihr auf eine Seite", () => {
    const e = einheitAus(0, [{ art: "titel", text: "Die Wolke" }, { art: "bild", bild: { adresse: "blob:b", verhaeltnis: 1, text: "" } }, { art: "absatz", text: "Sie schwebt." }]);
    const seiten = seitenAus(0, e.bloecke, seitenmass());
    expect(seiten).toHaveLength(1);
    expect(seiten[0].bild?.adresse).toBe("blob:b");
    expect(text(seiten[0].zeilen.map((z) => z.woerter))).toEqual(["Die Wolke", "Sie schwebt."]);
    expect(seiten[0].von).toBe(0);
  });

  it("lässt eine Überschrift nie allein unten stehen", () => {
    const e = einheitAus(0, [{ art: "absatz", text: "eins zwei drei" }, { art: "titel", text: "Zwei" }, { art: "absatz", text: "vier fünf" }]);
    const seiten = seitenAus(0, e.bloecke, seitenmass({ text: { breite: 400, hoehe: 120 } }));
    expect(seiten.map((s) => text(s.zeilen.map((z) => z.woerter)))).toEqual([["eins zwei drei"], ["Zwei", "vier fünf"]]);
  });

  it("baut Einheiten aus einem Text mit Leerzeilen und findet Wortlaute wieder", () => {
    const e = einheitAusText(3, "Titel\n\nDer erste Satz.\n\nDer zweite.", (von) => von === 0, [{ von: 7, bild: { adresse: "blob:b", verhaeltnis: null, text: "" } }]);
    expect(e.bloecke.map((b) => b.art)).toEqual(["titel", "bild", "absatz", "absatz"]);
    expect(lageVon(e.text, "erste   Satz")).toEqual({ von: 11, bis: 21 });
    expect(lageVon(e.text, "fehlt")).toBeNull();
  });
});

/** Ein Buch mit drei Einheiten zu je vier Zeilen Text; zwei Zeilen je Seite */
function probebuch(): Kinderquelle {
  const texte = ["a1 a2 a3 a4 a5 a6 a7 a8. a9 a10 a11 a12 a13 a14 a15 a16.", "", "c1 c2 c3 c4 c5 c6 c7 c8."];
  const einheiten: Einheit[] = texte.map((t, i) => einheitAus(i, t ? [{ art: "absatz", text: t }] : []));
  return {
    art: "txt", anzahl: einheiten.length, name: (e) => `Stück ${e + 1}`, einheit: async (n) => einheiten[n],
    lesewerte: async () => ({}), stelleAus: async () => null, markierungsort: async () => "", einheitDer: async () => null, ort: () => "", schliesse: () => {},
  };
}

function leser(griffe: Partial<Lesergriffe> = {}) {
  const gerueckt: number[] = [];
  const s = new Kinderlesestand(probebuch(), { ruheFaellig: () => false, ruhe: () => {}, gerueckt: (st) => gerueckt.push(st.einheit), wortgenau: () => false, ...griffe });
  return { s, gerueckt };
}

const lesemass = seitenmass({ text: { breite: 10_000, hoehe: 80 }, woerter: 4 });

describe("Kinderleser", () => {
  it("zeigt erst, wenn das Maß da ist, und beginnt an der gemerkten Stelle", async () => {
    const { s } = leser();
    await s.beginne({ einheit: 0, zeichen: 40 }, null);
    expect(s.jetzt).toBeNull();
    await s.setzeMass(lesemass);
    expect([s.einheit, s.seite]).toEqual([0, 1]);
    expect(s.jetzt?.zeilen.map((z) => z.woerter[0].text)).toEqual(["a9", "a13"]);
  });

  it("bewegt die Lesezeile durch Tippen: auf eine Zeile springt sie hin, auf sich selbst eine weiter", async () => {
    const { s } = leser();
    await s.setzeMass(lesemass);
    expect(s.zeile).toBe(0);
    s.tippeZeile(0);
    expect(s.zeile).toBe(1);
    s.tippeZeile(1);
    expect(s.zeile).toBe(1);
    s.tippeZeile(0);
    expect(s.zeile).toBe(0);
    s.setzeZeile(9);
    expect(s.zeile).toBe(1);
  });

  it("blättert über leere Einheiten hinweg, zurück auf die letzte Seite davor, und kennt das Ende", async () => {
    const { s, gerueckt } = leser();
    await s.setzeMass(lesemass);
    await s.weiter();
    expect([s.einheit, s.seite, s.zeile]).toEqual([0, 1, 0]);
    await s.weiter();
    expect([s.einheit, s.seite]).toEqual([2, 0]);
    await s.zurueck();
    expect([s.einheit, s.seite]).toEqual([0, 1]);
    await s.weiter();
    await s.weiter();
    await s.weiter();
    expect(s.amEnde).toBe(true);
    expect(gerueckt.length).toBeGreaterThan(3);
  });

  it("blättert nicht weiter, wenn die Ruhe fällig ist: die Seite endet, dann kommt sie", async () => {
    let faellig = false;
    const ruhe = vi.fn();
    const { s } = leser({ ruheFaellig: () => faellig, ruhe });
    await s.setzeMass(lesemass);
    faellig = true;
    await s.weiter();
    expect(ruhe).toHaveBeenCalledOnce();
    expect([s.einheit, s.seite]).toEqual([0, 0]);
  });

  it("setzt das eine Lesezeichen und nimmt es auf derselben Seite wieder weg", async () => {
    const { s } = leser();
    await s.setzeMass(lesemass);
    expect(s.lesezeichenUmschalten()).toEqual({ einheit: 0, zeichen: 0 });
    expect(s.aufLesezeichen).toBe(true);
    await s.weiter();
    expect(s.aufLesezeichen).toBe(false);
    await s.zumLesezeichen();
    expect(s.seite).toBe(0);
    expect(s.lesezeichenUmschalten()).toBeNull();
  });

  it("folgt beim Vorlesen: blättert am Ende der Seite weiter und zeigt das geschätzte Wort samt Lesezeile", async () => {
    const { s } = leser();
    await s.setzeMass(lesemass);
    const q = s.vorlesequelle();
    const text = await q.text(0);
    const satz = { einheit: 0, von: text.indexOf("a9"), bis: text.indexOf("a16.") + 4 };
    q.markiere(satz);
    await q.fuehre({ einheit: 0, zeichen: satz.von }, false);
    expect(s.seite).toBe(1);
    expect(s.wort).toBe(text.indexOf("a9"));
    // Etwa in der Mitte des Satzes: ein Wort der zweiten Zeile
    await q.fuehre({ einheit: 0, zeichen: satz.von + Math.round((satz.bis - satz.von) * 0.8) }, false);
    expect(s.zeile).toBe(1);
    q.markiere(null);
    expect(s.wort).toBe(-1);
  });

  it("nimmt bei Stimmen mit Wortgrenzen genau das Wort an der Stelle", async () => {
    const { s } = leser({ wortgenau: () => true });
    await s.setzeMass(lesemass);
    const q = s.vorlesequelle();
    const text = await q.text(0);
    q.markiere({ einheit: 0, von: 0, bis: 23 });
    await q.fuehre({ einheit: 0, zeichen: text.indexOf("a3") + 1 }, false);
    expect(s.wort).toBe(text.indexOf("a3"));
  });

  it("endet beim Vorlesen am Ende der Seite, wenn die Ruhe fällig ist", async () => {
    let faellig = false;
    const ruhe = vi.fn();
    const { s } = leser({ ruheFaellig: () => faellig, ruhe });
    await s.setzeMass(lesemass);
    const q = s.vorlesequelle();
    faellig = true;
    await q.fuehre({ einheit: 0, zeichen: 3 }, false);
    expect(ruhe).not.toHaveBeenCalled();
    await q.fuehre({ einheit: 0, zeichen: (await q.text(0)).indexOf("a9") }, false);
    expect(ruhe).toHaveBeenCalledOnce();
    expect(s.seite).toBe(0);
    await ruhe();
  });
});

describe("Mitlesen", () => {
  const w = woerterAus("Die Schmetterlinge fliegen, dann ruht der Wind.");

  it("findet das Wort an einer Stelle, zwischen Wörtern das nächste", () => {
    expect(wortBei(w, 0)).toBe(0);
    expect(wortBei(w, 3)).toBe(1);
    expect(wortBei(w, 999)).toBe(w.length - 1);
    expect(wortBei([], 0)).toBe(-1);
  });

  it("schätzt nach Silben und Pausen statt nach Buchstaben", () => {
    const silbe = (t: string) => ({ Die: 1, "Schmetterlinge": 4, "fliegen,": 2, dann: 1, ruht: 1, der: 1, "Wind.": 1 })[t] ?? 1;
    // Gesamt: 1 + 4 + 2 + 0,7 Pause + 1 + 1 + 1 + 1 = 11,7; ein Viertel liegt noch im langen Wort
    expect(geschaetztesWort(w, 0.25, silbe)).toBe(1);
    expect(geschaetztesWort(w, 0, silbe)).toBe(0);
    expect(geschaetztesWort(w, 1, silbe)).toBe(w.length - 1);
    expect(geschaetztesWort([], 0.5, silbe)).toBe(-1);
  });
});

afterAll(async () => {
  await ruhe();
});
