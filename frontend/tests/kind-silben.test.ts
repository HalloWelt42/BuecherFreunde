// Farbige Silben im Kinderleser (BF-78): deutsche Trennmuster und die Silben am Wortrand, die sie auslassen
import { hyphenateSync } from "hyphen/de-1996";
import { kernsilben, ladeSilbentrenner, silben, silbenAus, silbentrennerBereit, silbenzahl, wortteile } from "../src/lib/kind/silben";

const trenne = (w: string) => hyphenateSync(w, { hyphenChar: "­", minWordLength: 2 });
const s = (w: string) => silben(w, trenne).join("|");

describe("Silben", () => {
  it("trennt Wörter nach den deutschen Mustern", () => {
    expect(s("Bretter")).toBe("Bret|ter");
    expect(s("Schuppen")).toBe("Schup|pen");
    expect(s("Schmetterling")).toBe("Schmet|ter|ling");
    expect(s("Regenbogen")).toBe("Re|gen|bo|gen");
    expect(s("Zucker")).toBe("Zu|cker");
  });

  it("zählt einen einzelnen Selbstlaut am Wortanfang als Silbe", () => {
    expect(s("Ufer")).toBe("U|fer");
    expect(s("Oma")).toBe("O|ma");
    expect(s("aber")).toBe("a|ber");
    expect(s("Igel")).toBe("I|gel");
    expect(s("Ecke")).toBe("E|cke");
    expect(s("Abenteuer")).toBe("A|ben|teu|er");
  });

  it("trennt keinen Doppellaut und keinen Mitlaut ab", () => {
    expect(s("Eule")).toBe("Eu|le");
    expect(s("aus")).toBe("aus");
    expect(s("Apfel")).toBe("Ap|fel");
    expect(s("Ente")).toBe("En|te");
    expect(s("ich")).toBe("ich");
  });

  it("lässt nie eine Silbe ohne Selbstlaut stehen", () => {
    expect(silbenAus("Haus­s")).toEqual(["Hauss"]);
    expect(silbenAus("s­piel")).toEqual(["spiel"]);
  });

  it("trennt Teile mit Bindestrich je für sich", () => {
    expect(kernsilben("Erdbeer-Eis", trenne)).toEqual(["Erd", "beer-", "Eis"]);
  });

  it("teilt Satzzeichen vom Wortkern ab", () => {
    expect(wortteile("»Hallo,")).toEqual({ vor: "»", kern: "Hallo", nach: "," });
    expect(wortteile("Teich.")).toEqual({ vor: "", kern: "Teich", nach: "." });
  });

  it("bleibt ohne Trennmuster ganz und zählt dann Selbstlautgruppen", () => {
    expect(silben("Schuppen", null)).toEqual(["Schuppen"]);
    expect(silbenzahl("Schuppen.", null)).toBe(2);
    expect(silbenzahl("Schmetterling", trenne)).toBe(3);
  });

  it("lädt die Trennmuster erst auf Wunsch", async () => {
    await ladeSilbentrenner();
    expect(silbentrennerBereit()).toBe(true);
    expect(silben("Kaninchen").join("|")).toBe("Ka|nin|chen");
  });
});
