// Verweise auf PDF-Seiten (BF-125): Adressen im Text, Links der Datei, die Ebene zum Anklicken
import { adresseVon, adressenIn, dateiverweise, Ebenentext, verweisebene } from "../src/lib/leser/pdf/verweise";

describe("Adressen im Text", () => {
  it("findet Adressen mit und ohne Schema, ohne Satzzeichen am Ende", () => {
    const text = "Mehr unter https://beispiel.de/kapitel-3. Oder www.beispiel.org, dort (siehe https://beispiel.net/a_(b)).";
    expect(adressenIn(text).map((a) => a.adresse)).toEqual(["https://beispiel.de/kapitel-3", "https://www.beispiel.org/", "https://beispiel.net/a_(b)"]);
    const [erste] = adressenIn(text);
    expect(text.slice(...erste.stuecke[0])).toBe("https://beispiel.de/kapitel-3");
  });

  it("folgt einer Adresse über den Umbruch, wo sie sichtbar umbricht", () => {
    const text = "Siehe https://beispiel.de/ein/langer/\npfad/datei.html und weiter\nhttps://beispiel.de/ende\nNeue Zeile";
    const [a, b] = adressenIn(text);
    expect(a.adresse).toBe("https://beispiel.de/ein/langer/pfad/datei.html");
    expect(a.stuecke.map(([v, x]) => text.slice(v, x))).toEqual(["https://beispiel.de/ein/langer/", "pfad/datei.html"]);
    expect(b.adresse).toBe("https://beispiel.de/ende");
  });

  it("ein Punkt am Zeilenende schließt den Satz, die nächste Zeile gehört nicht dazu", () => {
    expect(adressenIn("liegen unter https://beispiel.de/kapitel-1.\nEine zweite Quelle").map((a) => a.adresse)).toEqual(["https://beispiel.de/kapitel-1"]);
  });

  it("nimmt nur Adressen nach außen, nichts anderes", () => {
    expect(adresseVon("javascript:alert(1)")).toBeNull();
    expect(adresseVon("https://localhost")).toBeNull();
    expect(adresseVon("mailto:post@beispiel.de")).toBe("mailto:post@beispiel.de");
    expect(adressenIn("Kein Link: http:// und www. allein")).toEqual([]);
  });
});

describe("Text der Ebene", () => {
  it("setzt die Stücke in Lesefolge zusammen, ein Zeilenende als Umbruch", () => {
    const ebene = document.createElement("div");
    ebene.innerHTML = '<span>Siehe https://beispiel.de/</span><br><span>pfad</span><span> danach</span>';
    const t = new Ebenentext(ebene);
    expect(t.text).toBe("Siehe https://beispiel.de/\npfad danach");
    const [a] = adressenIn(t.text);
    const r = t.bereich(...a.stuecke[1]);
    expect(r?.toString()).toBe("pfad");
    expect(t.bereich(...a.stuecke[0])?.toString()).toBe("https://beispiel.de/");
  });
});

describe("Links der Datei", () => {
  it("rechnet Flächen um und löst Ziele im Buch auf", async () => {
    const anmerkungen = [
      { subtype: "Link", rect: [10, 700, 110, 720], url: "https://beispiel.de/" },
      { subtype: "Link", rect: [10, 600, 60, 620], dest: "kapitel2" },
      { subtype: "Link", rect: [10, 500, 60, 520], url: "javascript:alert(1)" },
      { subtype: "Text", rect: [0, 0, 5, 5] },
    ];
    const v = await dateiverweise(anmerkungen, ([x1, y1, x2, y2]) => [x1, 800 - y1, x2, 800 - y2], async (z) => (z === "kapitel2" ? 7 : null));
    expect(v).toEqual([
      { ziel: { art: "adresse", adresse: "https://beispiel.de/" }, flaechen: [{ x: 10, y: 80, breite: 100, hoehe: 20 }] },
      { ziel: { art: "seite", seite: 7 }, flaechen: [{ x: 10, y: 180, breite: 50, hoehe: 20 }] },
    ]);
  });

  it("öffnet Adressen in neuem Fenster, Seiten springen im Buch", () => {
    const springe = vi.fn();
    const ebene = verweisebene(document, [
      { ziel: { art: "adresse", adresse: "https://beispiel.de/" }, flaechen: [{ x: 1, y: 2, breite: 3, hoehe: 4 }] },
      { ziel: { art: "seite", seite: 7 }, flaechen: [{ x: 5, y: 6, breite: 7, hoehe: 8 }] },
    ], springe);
    const [aussen, innen] = [...ebene.querySelectorAll("a")];
    expect([aussen.target, aussen.rel, aussen.style.left, aussen.style.height]).toEqual(["_blank", "noopener noreferrer", "1px", "4px"]);
    const klick = new MouseEvent("click", { bubbles: true, cancelable: true });
    innen.dispatchEvent(klick);
    expect(klick.defaultPrevented).toBe(true);
    expect(springe).toHaveBeenCalledWith(7);
  });
});
