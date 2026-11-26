import { folgensaetze } from "../src/ansichten/buch/loeschen";
import type { Loeschfolgen } from "../src/lib/typen";

const folgen = (anders: Partial<Loeschfolgen> = {}): Loeschfolgen => ({
  titel: "Der Prozeß", autor: "Franz Kafka", notizen: 0, markierungen: 0, etiketten: 0, lesestand: false, vorlesestelle: false, regale: 0,
  datei: null, abschnitte: null, ...anders,
});

describe("Folgen vor dem Löschen eines Buchs (BF-60)", () => {
  it("nennt alles, was es gibt, in ganzen Sätzen", () => {
    expect(folgensaetze(folgen({
      notizen: 3, markierungen: 12, etiketten: 2, lesestand: true, vorlesestelle: true, regale: 2, abschnitte: 1286,
      datei: { pfad: "Apps/BücherFreunde/Bücher/D/Der Prozeß.epub", groesse: 173000, papierkorb: true },
    }))).toEqual([
      "3 Notizen, 12 Markierungen und 2 Etiketten gehen verloren.",
      "Der Lesestand und die Stelle, an der das Vorlesen stehen blieb, gehen verloren.",
      "Das Buch fehlt danach in 2 Regalen.",
      "Die Datei kommt in den Papierkorb der Kellerwolke und lässt sich dort zurückholen: Apps/BücherFreunde/Bücher/D/Der Prozeß.epub, 173 KB.",
      "Die Suche nach Bedeutung vergisst das Buch (1.286 Abschnitte).",
    ]);
  });

  it("zählt richtig in der Einzahl", () => {
    expect(folgensaetze(folgen({ notizen: 1, regale: 1, abschnitte: 1 }))).toEqual([
      "1 Notiz geht verloren.", "Das Buch fehlt danach in 1 Regal.", "Die Suche nach Bedeutung vergisst das Buch (1 Abschnitt).",
    ]);
    expect(folgensaetze(folgen({ notizen: 1, etiketten: 1 }))[0]).toBe("1 Notiz und 1 Etikett gehen verloren.");
  });

  it("sagt, wenn die Datei nur hier liegt und danach fort ist", () => {
    expect(folgensaetze(folgen({ datei: { pfad: "Buch.pdf", groesse: 2500000, papierkorb: false }, vorlesestelle: true }))).toEqual([
      "Die Stelle, an der das Vorlesen stehen blieb, geht verloren.",
      "Die Datei liegt nur auf diesem Gerät und ist danach fort: Buch.pdf, 2,5 MB.",
    ]);
  });

  it("nennt nichts, was es nicht gibt", () => {
    expect(folgensaetze(folgen())).toEqual([]);
  });
});
