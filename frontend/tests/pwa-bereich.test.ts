// BF-78: Bereichsanfragen im Dienst im Hintergrund. Safari fragt einen Ton zuerst mit "Range: bytes=0-1" an und spielt ihn nur
// mit einer Teilantwort (206); kam das Schnurren der Katze ganz aus dem Vorrat (200), blieb es auf dem iPad stumm. Geprüft wird
// public/sw.js selbst, in einem Rahmen mit eigenem Speicher und eigenem Netz statt des Browsers.
const dateien = import.meta.glob<string>("../public/sw.js", { query: "?raw", import: "default", eager: true });
const code = Object.values(dateien)[0];

const URSPRUNG = "https://buecher.probe.test";
const TON = `${URSPRUNG}/assets/schnurren-Probe01.mp3`;
const GROESSE = 1000;
const ton = () => new Response(new Uint8Array(GROESSE).map((_, i) => i % 251), { status: 200, headers: { "Content-Type": "audio/mpeg" } });

/** Ein Speicher wie im Browser: ein Stück (206) nimmt er nicht an */
class Speicher {
  eintraege = new Map<string, Response>();
  async match(anfrage: Request | string) {
    return this.eintraege.get(typeof anfrage === "string" ? anfrage : anfrage.url)?.clone();
  }
  async put(anfrage: Request | string, antwort: Response) {
    if (antwort.status === 206) throw new TypeError("Partial response (status code 206) is unsupported");
    this.eintraege.set(typeof anfrage === "string" ? anfrage : anfrage.url, antwort);
  }
  async keys() {
    return [...this.eintraege.keys()].map((u) => new Request(u));
  }
  async delete(anfrage: Request) {
    return this.eintraege.delete(anfrage.url);
  }
}

/** sw.js mit eigenem Speicher und eigenem Netz; gibt die Antwort auf eine Anfrage zurück */
function dienst(netz: (anfrage: Request) => Promise<Response>) {
  const speicher = new Map<string, Speicher>();
  const oeffne = async (name: string) => speicher.get(name) ?? speicher.set(name, new Speicher()).get(name)!;
  const caches = {
    open: oeffne,
    keys: async () => [...speicher.keys()],
    delete: async (name: string) => speicher.delete(name),
    match: async (anfrage: Request | string) => {
      for (const s of speicher.values()) {
        const da = await s.match(anfrage);
        if (da) return da;
      }
      return undefined;
    },
  };
  const abrufe: Request[] = [];
  const handler: Record<string, (e: unknown) => void> = {};
  const self = { addEventListener: (art: string, tun: (e: unknown) => void) => (handler[art] = tun), skipWaiting: async () => {}, clients: { claim: async () => {} } };
  new Function("self", "caches", "fetch", "location", code)(self, caches, (a: Request) => (abrufe.push(a), netz(a)), { origin: URSPRUNG });
  return {
    abrufe,
    speicher: oeffne,
    async frage(url: string, kopf: Record<string, string> = {}): Promise<Response> {
      let antwort: Promise<Response> | undefined;
      handler.fetch({ request: new Request(url, { headers: kopf }), respondWith: (p: Promise<Response>) => (antwort = p), waitUntil: () => {} });
      if (!antwort) throw new Error("Der Dienst hat nicht geantwortet");
      return antwort;
    },
  };
}

const bytes = async (r: Response) => [...new Uint8Array(await r.arrayBuffer())];

describe("Bereichsanfragen aus dem Vorrat", () => {
  const imVorrat = async () => {
    const d = dienst(async () => {
      throw new Error("Das Netz wird nicht gebraucht");
    });
    await (await d.speicher("bau-probe")).put(TON, ton());
    return d;
  };

  it("das erste Stück, wie Safari es für einen Ton erfragt, kommt als 206 mit Content-Range", async () => {
    const d = await imVorrat();
    const r = await d.frage(TON, { Range: "bytes=0-1" });
    expect(r.status).toBe(206);
    expect(r.headers.get("content-range")).toBe(`bytes 0-1/${GROESSE}`);
    expect(r.headers.get("content-length")).toBe("2");
    expect(r.headers.get("content-type")).toBe("audio/mpeg");
    expect(await bytes(r)).toEqual([0, 1]);
    expect(d.abrufe).toEqual([]);
  });

  it("offene und mittlere Bereiche bekommen genau ihre Bytes", async () => {
    const d = await imVorrat();
    const rest = await d.frage(TON, { Range: "bytes=0-" });
    expect([rest.status, rest.headers.get("content-range")]).toEqual([206, `bytes 0-${GROESSE - 1}/${GROESSE}`]);
    expect((await bytes(rest)).length).toBe(GROESSE);
    const mitte = await d.frage(TON, { Range: "bytes=500-502" });
    expect([mitte.status, mitte.headers.get("content-range")]).toEqual([206, `bytes 500-502/${GROESSE}`]);
    expect(await bytes(mitte)).toEqual([500 % 251, 501 % 251, 502 % 251]);
    const ueber = await d.frage(TON, { Range: "bytes=900-5000" });
    expect(ueber.headers.get("content-range")).toBe(`bytes 900-${GROESSE - 1}/${GROESSE}`);
  });

  it("ohne Bereich bleibt es die ganze Datei, hinter dem Ende sagt 416 die Größe", async () => {
    const d = await imVorrat();
    const ganz = await d.frage(TON);
    expect([ganz.status, (await bytes(ganz)).length]).toEqual([200, GROESSE]);
    const hinten = await d.frage(TON, { Range: `bytes=${GROESSE}-` });
    expect([hinten.status, hinten.headers.get("content-range")]).toEqual([416, `bytes */${GROESSE}`]);
  });
});

describe("Bereichsanfragen über das Netz", () => {
  it("eine Teilantwort des Servers geht durch und wird nicht gemerkt", async () => {
    const d = dienst(async () => new Response(new Uint8Array([7, 8]), { status: 206, headers: { "Content-Range": `bytes 0-1/${GROESSE}` } }));
    const r = await d.frage(TON, { Range: "bytes=0-1" });
    expect([r.status, r.headers.get("content-range"), await bytes(r)]).toEqual([206, `bytes 0-1/${GROESSE}`, [7, 8]]);
    expect(await (await d.speicher("bau-__FASSUNG__")).match(TON)).toBeUndefined();
  });

  it("schickt der Server trotz Bereich die ganze Datei, wird sie gemerkt und das Stück geht hinaus", async () => {
    const d = dienst(async () => ton());
    const r = await d.frage(TON, { Range: "bytes=0-1" });
    expect([r.status, await bytes(r)]).toEqual([206, [0, 1]]);
    const gemerkt = await (await d.speicher("bau-__FASSUNG__")).match(TON);
    expect(gemerkt?.status).toBe(200);
    expect(d.abrufe.map((a) => a.headers.get("range"))).toEqual(["bytes=0-1"]);
  });
});

describe("Gemerkter Lesestoff ohne Netz", () => {
  it("ein Bereich der Buchdatei kommt weiter als Stück", async () => {
    const d = dienst(async () => {
      throw new TypeError("ohne Netz");
    });
    const datei = `${URSPRUNG}/api/books/3/file`;
    await (await d.speicher("lesestoff")).put(datei, new Response(new Uint8Array([1, 2, 3, 4, 5]), { status: 200, headers: { "Content-Type": "application/pdf" } }));
    const r = await d.frage(datei, { Range: "bytes=1-3" });
    expect([r.status, r.headers.get("content-range"), r.headers.get("content-type"), await bytes(r)]).toEqual([206, "bytes 1-3/5", "application/pdf", [2, 3, 4]]);
  });
});
