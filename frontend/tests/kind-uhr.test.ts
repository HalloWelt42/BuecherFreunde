// Die Kinderuhr (BF-78, Entwurf Runde 3): Zeiger, das farbige Stück der Lesezeit, voller Kreis ab 60 Minuten, früheres Ende bei
// Ruhezeit, Wechsel nur am Minutenwechsel
import { Minutentakt } from "../src/lib/kind/minutentakt.svelte";
import { minutenBis, ort, restMinuten, striche, stueckMinuten, stueckPfad, uhrtext, zahlen, zeigerwinkel } from "../src/lib/kind/uhr";

describe("Kinderuhr", () => {
  it("stellt die Zeiger: Minuten je 6 Grad, Stunden je 30 Grad und mit den Minuten weiter", () => {
    expect(zeigerwinkel(0, 0)).toEqual({ stunde: 0, minute: 0 });
    expect(zeigerwinkel(16, 35).minute % 360).toBe(210);
    expect(zeigerwinkel(16, 35).stunde % 360).toBe(137.5);
    // Über den Tag stetig: von 9:59 auf 10:00 dreht der Minutenzeiger vorwärts
    expect(zeigerwinkel(10, 0).minute).toBeGreaterThan(zeigerwinkel(9, 59).minute);
  });

  it("findet Orte auf dem Zifferblatt: 12 oben, 3 rechts", () => {
    expect(ort(0, 44)).toEqual([50, 6]);
    expect(ort(15, 44)).toEqual([94, 50]);
    expect(ort(30, 30)).toEqual([50, 80]);
  });

  it("zeichnet das Stück vom Minutenzeiger bis zum Ende der Lesezeit", () => {
    expect(stueckPfad(0, 15)).toBe("M50 50L50 6A44 44 0 0 1 94 50Z");
    // Mehr als eine halbe Stunde: der große Bogen
    expect(stueckPfad(0, 45)).toContain("A44 44 0 1 1");
    expect(stueckPfad(10, 0)).toBeNull();
  });

  it("füllt ab 60 Minuten den ganzen Kreis", () => {
    expect(stueckMinuten(90, null)).toBe(60);
    expect(stueckPfad(20, stueckMinuten(90, null))).toBeNull();
  });

  it("endet früher, wenn die Ruhezeit vor dem Ende der Lesezeit beginnt", () => {
    const jetzt = new Date(2026, 10, 26, 19, 10);
    expect(minutenBis("19:30", jetzt)).toBe(20);
    expect(stueckMinuten(45, minutenBis("19:30", jetzt))).toBe(20);
    expect(stueckMinuten(10, minutenBis("19:30", jetzt))).toBe(10);
    // Schon vorbei: die nächste Ruhezeit kommt morgen
    expect(minutenBis("19:00", jetzt)).toBe(23 * 60 + 50);
    expect(minutenBis(new Date(2026, 10, 26, 19, 40).toISOString(), jetzt)).toBe(30);
    expect(minutenBis(null, jetzt)).toBeNull();
  });

  it("hat in der großen Uhr einen Strich je Minute und zwölf Zahlen, in der kleinen nur die Stunden", () => {
    expect(striche(true)).toHaveLength(60);
    expect(striche(false)).toHaveLength(12);
    expect(striche(false).every((s) => s.stunde)).toBe(true);
    expect(zahlen().map((z) => z.zahl)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    expect(zahlen()[11].bei).toEqual([50, 20]);
  });

  it("sagt, was sie zeigt, und zählt angefangene Minuten mit", () => {
    expect(uhrtext(16, 35, 25)).toBe("Es ist 4 Uhr 35, noch 25 Minuten lesen");
    expect(uhrtext(12, 0, 1)).toBe("Es ist 12 Uhr, noch 1 Minute lesen");
    expect(restMinuten(30)).toBe(1);
    expect(restMinuten(1500)).toBe(25);
    expect(restMinuten(-5)).toBe(0);
  });

  it("schlägt nur am Minutenwechsel der Uhr des Geräts", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 26, 16, 35, 40));
    const takt = new Minutentakt();
    const ende = takt.beobachte();
    expect(takt.jetzt.getMinutes()).toBe(35);
    vi.advanceTimersByTime(19_000);
    expect(takt.jetzt.getMinutes()).toBe(35);
    vi.advanceTimersByTime(1_100);
    expect(takt.jetzt.getMinutes()).toBe(36);
    expect(takt.jetzt.getSeconds()).toBe(0);
    vi.advanceTimersByTime(59_000);
    expect(takt.jetzt.getMinutes()).toBe(36);
    vi.advanceTimersByTime(1_100);
    expect(takt.jetzt.getMinutes()).toBe(37);
    ende();
    vi.advanceTimersByTime(120_000);
    expect(takt.jetzt.getMinutes()).toBe(37);
    vi.useRealTimers();
  });
});
