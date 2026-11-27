// BF-109: Seiten eines Scans, deren Text die Texterkennung noch liest, warten mit drehendem Zeichen; die Textansicht bittet für
// die gelesene Seite um Vorrang, fragt sanft nach (wachsender Abstand, nie Dauerfeuer) und holt erkannte Seiten an ihrer Stelle neu.
import type { Vorrangstand } from "../src/lib/api/books";
import { ABSTAENDE_MS, Erkennungswarten, type Wartelage } from "../src/lib/leser/pdf/erkennungswarten";
import { Textseiten, type Schicht, type Textantwort, type Textseite } from "../src/lib/leser/pdf/textseiten.svelte";

const absatz = (text: string) => ({ art: "absatz" as const, text, titel: "", inhalt: [], bild: null, verhaeltnis: null, breite_em: null });
const seitenbild = { art: "bild" as const, text: "", titel: "", inhalt: [], bild: 0, verhaeltnis: 0.7, breite_em: null };
const seite = (nr: number, schicht: Schicht, text = ""): Textseite =>
  ({ nr, gedruckt: "", bausteine: text ? [absatz(text)] : [seitenbild], schicht });

describe("Textseiten mit Texterkennung", () => {
  it("warten nur auf Seiten in der Erkennung; ohne Text und ohne Erkennung bleibt der Hinweis", async () => {
    const mit = (...seiten: Textseite[]) => new Textseiten(1, async (tun) => void tun(), async () => ({ gesamt: 3, seiten }));
    const scan = mit(seite(1, "wartet"), seite(2, "wartet"), seite(3, "ohne"));
    await scan.neu(1);
    const ohne = mit(seite(1, "ohne"), seite(2, "ohne"));
    await ohne.neu(1);
    expect([scan.wartend, scan.ohneText]).toEqual([[1, 2], false]);
    expect([ohne.wartend, ohne.ohneText]).toEqual([[], true]);
  });

  it("setzen erkannte Seiten an ihrer Stelle ein, mit den Nachbarseiten, ohne die übrigen anzufassen", async () => {
    const geholt: [number, number][] = [];
    let erkannt = false;
    const hole = async (_b: number, ab: number, anzahl: number): Promise<Textantwort> => {
      geholt.push([ab, anzahl]);
      const nrn = Array.from({ length: anzahl }, (_, i) => ab + i).filter((n) => n <= 8);
      return { gesamt: 8, seiten: nrn.map((n) => (n === 5 && !erkannt ? seite(n, "wartet") : seite(n, n === 5 ? "erkannt" : "pdf", `Seite ${n}${erkannt ? " neu" : ""}`))) };
    };
    const t = new Textseiten(1, async (tun) => void tun(), hole);
    await t.neu(2);
    expect(t.wartend).toEqual([5]);
    erkannt = true;
    expect(await t.erneuere([5, 9])).toBe(true);
    expect(geholt.at(-1)).toEqual([4, 3]);
    expect(t.seiten.map((s) => [s.nr, s.schicht, s.bausteine[0].text])).toEqual([
      [2, "pdf", "Seite 2"], [3, "pdf", "Seite 3"], [4, "pdf", "Seite 4 neu"], [5, "erkannt", "Seite 5 neu"], [6, "pdf", "Seite 6 neu"],
      [7, "pdf", "Seite 7"]]);
    expect(t.wartend).toEqual([]);
    expect(await t.erneuere([12])).toBe(false);
  });
});

describe("Warten auf die Texterkennung", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  function aufbau(wartend: number[], antworten: (seite: number, mal: number) => Vorrangstand) {
    const lage: Wartelage = { wartend: [...wartend], gelesen: wartend[0] ?? 1 };
    const gefragt: number[] = [];
    const neu: number[][] = [];
    const w = new Erkennungswarten(7, () => lage, async (nrn) => {
      neu.push(nrn);
      lage.wartend = lage.wartend.filter((n) => !nrn.includes(n));
    }, async (_buch, seite) => {
      gefragt.push(seite);
      return antworten(seite, gefragt.length);
    });
    return { w, lage, gefragt, neu };
  }

  const stand = (von: number, wartet: number[], bereit = true): Vorrangstand => ({ bereit, grund: bereit ? "" : "nicht eingerichtet", von, bis: von + 5, wartet });

  it("bittet sofort um Vorrang und fragt dann im wachsenden Abstand nach, bis die Seiten da sind", async () => {
    const { w, gefragt, neu } = aufbau([10, 11], (s, mal) => stand(s, mal < 4 ? [10, 11] : mal === 4 ? [11] : []));
    w.pruefe();
    await vi.advanceTimersByTimeAsync(0);
    expect(gefragt).toEqual([10]);
    await vi.advanceTimersByTimeAsync(ABSTAENDE_MS[0]);
    expect(gefragt.length).toBe(2);
    await vi.advanceTimersByTimeAsync(ABSTAENDE_MS[1] - 1);
    expect(gefragt.length).toBe(2);                        // länger gewartet als beim ersten Mal
    await vi.advanceTimersByTimeAsync(1);
    expect(gefragt.length).toBe(3);
    await vi.advanceTimersByTimeAsync(ABSTAENDE_MS[2]);
    expect(neu).toEqual([[10]]);                           // Seite 10 ist erkannt und kommt neu
    await vi.advanceTimersByTimeAsync(ABSTAENDE_MS[0]);    // nach einer erkannten Seite wieder vorn
    expect(gefragt).toEqual([10, 10, 10, 10, 11]);
    expect(neu).toEqual([[10], [11]]);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(gefragt.length).toBe(5);                        // nichts wartet mehr: keine Frage mehr
  });

  it("fragt nie öfter als im kürzesten Abstand, auch wenn die gelesene Seite wechselt", async () => {
    const { w, lage, gefragt } = aufbau([3, 4, 5, 6], (s) => stand(s, [3, 4, 5, 6]));
    w.pruefe();
    await vi.advanceTimersByTimeAsync(0);
    for (const gelesen of [4, 5, 6]) {
      lage.gelesen = gelesen;
      w.pruefe();
      await vi.advanceTimersByTimeAsync(200);
    }
    expect(gefragt).toEqual([3]);
    await vi.advanceTimersByTimeAsync(ABSTAENDE_MS[0]);
    expect(gefragt).toEqual([3, 6]);                       // die zuletzt gelesene
    w.halte();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(gefragt).toEqual([3, 6]);
  });

  it("holt ohne bereite Texterkennung alle wartenden Seiten neu (dann mit dem Hinweis von heute)", async () => {
    const { w, gefragt, neu } = aufbau([8, 9], (s) => stand(s, [], false));
    w.pruefe();
    await vi.advanceTimersByTimeAsync(0);
    expect(gefragt).toEqual([8]);
    expect(neu).toEqual([[8, 9]]);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(gefragt).toEqual([8]);
  });

  it("fragt nach einer Störung später wieder", async () => {
    let gestoert = true;
    const { w, gefragt, neu } = aufbau([2], (s) => {
      if (gestoert) throw new Error("weg");
      return stand(s, []);
    });
    w.pruefe();
    await vi.advanceTimersByTimeAsync(0);
    gestoert = false;
    await vi.advanceTimersByTimeAsync(ABSTAENDE_MS[1]);
    expect(gefragt).toEqual([2, 2]);
    expect(neu).toEqual([[2]]);
  });
});
