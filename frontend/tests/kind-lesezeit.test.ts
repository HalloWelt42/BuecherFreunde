// Lesezeit im Kinderbereich (BF-78): gezählt wird nur beim Lesen, gemeldet im Takt, entschieden vom Server
import { faelligVon, hinweisVon, LEERLAUF_S, Lesezeituhr, restVon, TAKT_S, weiterAb } from "../src/lib/kind/lesezeit.svelte";
import { nochZeit, wannGelesen } from "../src/lib/kind/datum";
import type { Lesezeitstand } from "../src/lib/kind/typen";

const stand = (teil: Partial<Lesezeitstand> = {}): Lesezeitstand => ({ heute_s: 0, grenze_s: 600, rest_s: 600, ruht: false, ruhe_bis: null, ruhe_ab: null, hinweis_ab_s: 300, ...teil });

function uhr(start: Lesezeitstand = stand(), antwort?: (s: number) => Lesezeitstand) {
  let jetzt = 1_000_000;
  let sichtbar = true;
  const meldungen: [number, boolean][] = [];
  let rest = start.rest_s ?? 0;
  const u = new Lesezeituhr({
    melde: async (sekunden, vorlesen) => {
      meldungen.push([sekunden, vorlesen]);
      rest -= sekunden;
      return antwort ? antwort(sekunden) : stand({ rest_s: rest, heute_s: 600 - rest });
    },
    jetzt: () => jetzt,
    sichtbar: () => sichtbar,
  }, start);
  const sekunden = async (n: number) => {
    for (let i = 0; i < n; i++) {
      jetzt += 1000;
      u.schritt();
      await Promise.resolve();
      await Promise.resolve();
    }
  };
  return { u, meldungen, sekunden, verdecke: () => (sichtbar = false), zeige: () => (sichtbar = true), warte: (s: number) => (jetzt += s * 1000) };
}

describe("Lesezeit", () => {
  it("zählt nur, solange der Leser offen und zu sehen ist", async () => {
    const { u, sekunden, verdecke } = uhr();
    await sekunden(5);
    expect(u.offen).toBe(0);
    u.liest = true;
    await sekunden(5);
    expect(u.offen).toBe(5);
    verdecke();
    await sekunden(5);
    expect(u.offen).toBe(5);
    expect(u.rest).toBe(595);
  });

  it("meldet im Takt und übernimmt den Stand des Servers", async () => {
    const { u, meldungen, sekunden } = uhr();
    u.liest = true;
    await sekunden(TAKT_S);
    expect(meldungen).toEqual([[TAKT_S, false]]);
    expect(u.offen).toBe(0);
    expect(u.stand.rest_s).toBe(600 - TAKT_S);
  });

  it("trennt Lesen und Vorlesen in eigene Meldungen", async () => {
    const { u, meldungen, sekunden } = uhr();
    u.liest = true;
    await sekunden(3);
    u.vorliest = true;
    await sekunden(2);
    expect(meldungen).toEqual([[3, false]]);
    await u.melde();
    expect(meldungen).toEqual([[3, false], [2, true]]);
  });

  it("hört ohne Bedienung auf zu zählen, beim Vorlesen nicht", async () => {
    const { u, meldungen, sekunden, warte } = uhr();
    u.liest = true;
    warte(LEERLAUF_S + 1);
    await sekunden(3);
    expect(u.offen).toBe(0);
    u.vorliest = true;
    await sekunden(3);
    expect(u.offen).toBe(3);
    u.vorliest = false;
    u.regung();
    await sekunden(2);
    // Der Wechsel vom Vorlesen zum Lesen meldet das Vorgelesene für sich
    expect(meldungen).toEqual([[3, true]]);
    expect(u.offen).toBe(2);
  });

  it("meldet sofort, wenn hier nichts mehr bleibt; fällig ist es erst, wenn der Server es sagt", async () => {
    const { u, meldungen, sekunden } = uhr(stand({ rest_s: 4 }), (s) => stand({ rest_s: 4 - s }));
    u.liest = true;
    await sekunden(3);
    expect(u.faellig).toBe(false);
    await sekunden(1);
    expect(meldungen).toEqual([[4, false]]);
    expect(u.faellig).toBe(true);
  });

  it("behält Gezähltes, wenn die Meldung scheitert", async () => {
    const u = new Lesezeituhr({ melde: async () => Promise.reject(new Error("weg")), jetzt: () => 0, sichtbar: () => true }, stand());
    u.liest = true;
    u.regung();
    u.schritt();
    u.schritt();
    await u.melde();
    expect(u.offen).toBe(2);
  });

  it("rechnet Rest, Fälligkeit und Hinweis", () => {
    expect(restVon(stand({ rest_s: null }), 10)).toBeNull();
    expect(restVon(stand({ rest_s: 5 }), 10)).toBe(0);
    expect(faelligVon(stand({ ruht: true }))).toBe(true);
    expect(faelligVon(stand({ rest_s: 0 }))).toBe(true);
    expect(faelligVon(stand({ rest_s: null }))).toBe(false);
    // hinweis_ab_s zählt gelesene Zeit heute (fünf Minuten vor der Grenze), samt dem noch nicht Gemeldeten
    expect(hinweisVon(stand({ heute_s: 290, rest_s: 310 }), 10)).toBe(true);
    expect(hinweisVon(stand({ heute_s: 290, rest_s: 310 }), 5)).toBe(false);
    expect(hinweisVon(stand({ hinweis_ab_s: null }), 10)).toBe(false);
    expect(hinweisVon(stand({ heute_s: 600, rest_s: 0 }), 0)).toBe(false);
    expect(hinweisVon(stand({ heute_s: 400, rest_s: 200, ruht: true }), 0)).toBe(false);
  });

  it("sagt kindgerecht, wann es weitergeht und wie viel Zeit bleibt", () => {
    const jetzt = new Date(2026, 10, 26, 19, 40);
    expect(weiterAb(new Date(2026, 10, 27, 7, 0).toISOString(), jetzt)).toBe("Morgen ab 7 Uhr");
    expect(weiterAb(new Date(2026, 10, 26, 20, 30).toISOString(), jetzt)).toBe("Ab 20:30 Uhr");
    expect(weiterAb(null, jetzt)).toBe("Morgen");
    // Der Server nennt nur die Uhrzeit
    expect(weiterAb("06:30", jetzt)).toBe("Morgen ab 6:30 Uhr");
    expect(weiterAb("20:00", jetzt)).toBe("Ab 20 Uhr");
    expect(nochZeit(25 * 60)).toBe("noch 25 Minuten");
    expect(nochZeit(30)).toBe("noch 1 Minute");
    expect(nochZeit(70 * 60)).toBe("noch 1 Stunde 10 Minuten");
    expect(wannGelesen(new Date(2026, 10, 25, 10).toISOString(), jetzt)).toBe("gestern");
    expect(wannGelesen(new Date(2026, 9, 3).toISOString(), jetzt)).toBe("im Oktober");
    expect(wannGelesen(null, jetzt)).toBe("");
  });
});
