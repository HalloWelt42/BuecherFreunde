import { Hochlader } from "../src/lib/annahme/hochlader";
import { AndererStand, OhneVerbindung, type AnnahmeDienst, type AnnahmeEintrag, type Hochladung } from "../src/lib/annahme/typen";

const TEIL = 4;

function eintrag(ueber: Partial<AnnahmeEintrag> = {}): AnnahmeEintrag {
  return { id: 7, name: "Buch.epub", groesse: 10, sha256: "abc", empfangen: 0, teil_groesse: TEIL, stand: "wartet", schritt: 1, anteil: 0, text: "Bereit", buch_id: null, quelle: "hochladen", angelegt_am: "", geaendert_am: "", ...ueber };
}

/** Nachgebauter Server: merkt sich den Stand und wer wie viel zugleich schickt */
class Server implements AnnahmeDienst {
  stand_ = eintrag();
  gesendet: number[] = [];
  stoerung: ((ab: number) => Error | null) | null = null;
  zugleich = 0;
  hoechstensZugleich = 0;
  angelegt: string[] = [];

  anlegen = async (d: { name: string; groesse: number; sha256: string }) => {
    this.angelegt.push(`${d.name}/${d.sha256}`);
    this.stand_ = { ...this.stand_, id: this.angelegt.length, name: d.name, groesse: d.groesse };
    return this.stand_;
  };
  stand = async () => this.stand_;
  teil = async (_id: number, ab: number, inhalt: Blob, abbruch: AbortSignal) => {
    this.zugleich++;
    this.hoechstensZugleich = Math.max(this.hoechstensZugleich, this.zugleich);
    await new Promise((r) => setTimeout(r, 1));
    this.zugleich--;
    abbruch.throwIfAborted();
    const fehler = this.stoerung?.(ab);
    if (fehler) throw fehler;
    this.gesendet.push(ab);
    const empfangen = ab + inhalt.size;
    this.stand_ = { ...this.stand_, empfangen, stand: empfangen >= this.stand_.groesse ? "liest" : "laedt" };
    return this.stand_;
  };
}

const datei = (name = "Buch.epub", groesse = 10) => new File([new Uint8Array(groesse)], name);
const summe = async () => "abc";

function aufbau(server: AnnahmeDienst, warte: (ms: number) => Promise<void> = async () => {}) {
  const hochlader = new Hochlader(server, summe, { pausenMs: [1], warte });
  const bis = (pruefe: (l: Hochladung[]) => boolean) =>
    new Promise<Hochladung[]>((r, f) => {
      const uhr = setTimeout(() => f(new Error(`nie erreicht: ${JSON.stringify(hochlader.liste)}`)), 2000);
      const ab = hochlader.beiAenderung((l) => {
        if (!pruefe(l)) return;
        clearTimeout(uhr);
        ab();
        r(l);
      });
    });
  return { hochlader, bis };
}

const fertig = (l: Hochladung[]) => l.length > 0 && l.every((h) => h.lage === "beim_server");

describe("Hochlader", () => {
  it("schickt die Datei in Teilen nacheinander", async () => {
    const server = new Server();
    const { hochlader, bis } = aufbau(server);
    const ende = bis(fertig);
    hochlader.fuegeHinzu([datei()]);
    await ende;
    expect(server.gesendet).toEqual([0, 4, 8]);
    expect(server.angelegt).toEqual(["Buch.epub/abc"]);
  });

  it("schickt nichts, wenn es das Buch schon gibt", async () => {
    const server = new Server();
    server.stand_ = eintrag({ stand: "da", buch_id: 3 });
    const { hochlader, bis } = aufbau(server);
    const ende = bis(fertig);
    hochlader.fuegeHinzu([datei()]);
    await ende;
    expect(server.gesendet).toEqual([]);
  });

  it("setzt am Stand des Servers fort", async () => {
    const server = new Server();
    server.stand_ = eintrag({ empfangen: 4, stand: "angehalten" });
    const { hochlader, bis } = aufbau(server);
    const ende = bis(fertig);
    hochlader.fuegeHinzu([datei()]);
    await ende;
    expect(server.gesendet).toEqual([4, 8]);
  });

  it("glaubt dem Server, wenn er an anderer Stelle steht (409)", async () => {
    const server = new Server();
    let einmal = true;
    server.stoerung = (ab) => (ab === 4 && einmal ? ((einmal = false), new AndererStand(8)) : null);
    const { hochlader, bis } = aufbau(server);
    const ende = bis(fertig);
    hochlader.fuegeHinzu([datei()]);
    await ende;
    expect(server.gesendet).toEqual([0, 8]);
  });

  it("wartet nach einem Abriss und fragt nach dem Stand", async () => {
    const server = new Server();
    let stoerungen = 2;
    server.stoerung = (ab) => (ab === 4 && stoerungen-- > 0 ? new OhneVerbindung("weg") : null);
    const pausen: number[] = [];
    const { hochlader, bis } = aufbau(server, async (ms) => void pausen.push(ms));
    const ende = bis(fertig);
    hochlader.fuegeHinzu([datei()]);
    await ende;
    expect(server.gesendet).toEqual([0, 4, 8]);
    expect(pausen).toHaveLength(2);
  });

  it("schickt nicht ohne Pause weiter, wenn der Server nicht vorankommt", async () => {
    const server = new Server();
    let mal = 0;
    server.stoerung = (ab) => (ab === 4 && mal++ < 3 ? new AndererStand(4) : null);
    const pausen: number[] = [];
    const { hochlader, bis } = aufbau(server, async (ms) => void pausen.push(ms));
    const ende = bis(fertig);
    hochlader.fuegeHinzu([datei()]);
    await ende;
    expect(pausen).toHaveLength(3);
  });

  it("nennt den Grund, wenn der Server ablehnt", async () => {
    const server = new Server();
    server.stoerung = () => new Error("Kein Platz mehr");
    const { hochlader, bis } = aufbau(server);
    const ende = bis((l) => l[0]?.lage === "fehler");
    hochlader.fuegeHinzu([datei()]);
    expect((await ende)[0].text).toBe("Kein Platz mehr");
  });

  it("hält an und geht auf Wunsch weiter", async () => {
    const server = new Server();
    const { hochlader, bis } = aufbau(server);
    const laeuft = bis((l) => l[0]?.lage === "laedt" && l[0].gesendet > 0);
    hochlader.fuegeHinzu([datei()]);
    const [h] = await laeuft;
    hochlader.anhalten(h.schluessel);
    await new Promise((r) => setTimeout(r, 10));
    expect(hochlader.liste[0].lage).toBe("angehalten");
    expect(hochlader.laeuft).toBe(false);
    const ende = bis(fertig);
    hochlader.weiter(h.schluessel);
    await ende;
    expect(server.stand_.empfangen).toBe(10);
  });

  it("dieselbe Datei noch einmal gewählt setzt die angehaltene fort", async () => {
    const server = new Server();
    const { hochlader, bis } = aufbau(server);
    const laeuft = bis((l) => l[0]?.lage === "laedt");
    hochlader.fuegeHinzu([datei()]);
    const [h] = await laeuft;
    hochlader.anhalten(h.schluessel);
    const ende = bis(fertig);
    hochlader.fuegeHinzu([datei()]);
    expect((await ende).length).toBe(1);
  });

  it("bearbeitet höchstens zwei Dateien zugleich", async () => {
    const server = new Server();
    const { hochlader, bis } = aufbau(server);
    const ende = bis((l) => l.length === 5 && fertig(l));
    hochlader.fuegeHinzu([1, 2, 3, 4, 5].map((n) => datei(`Buch ${n}.epub`)));
    await ende;
    expect(server.hoechstensZugleich).toBeLessThanOrEqual(2);
    expect(server.angelegt).toHaveLength(5);
  });
});
