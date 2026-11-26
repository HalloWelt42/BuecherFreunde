// Vorlesen: welche Stimmen es gibt, welche gilt, was gerade klingt, und der Spieler dazu. Ist ein Sprechdienst angeschlossen,
// spricht nur er; sonst die Stimmen des Geräts. Beide hinter derselben Schnittstelle (lib/vorlesen).
// Liest es aus einem Buch, merkt der Server die Stelle (BF-37): Anhalten, Pause, Schlafuhr, Schließen des Buchs und Abriss
// sichern den Satz, an dem es stand, beim Lesen alle paar Sekunden auch; ist der gewählte Umfang zu Ende, ist sie weg.
import { holeVorlesestelle, ladeDienststimmen, merkeVorlesestelle, vergissVorlesestelle, type Dienststimmen, type Vorlesestelle } from "../api/vorlesen";
import { lies as gemerkt, merke } from "../speicher";
import { Dienstsprecher } from "../vorlesen/dienst";
import { Vorlesefolge, type Schlaf } from "../vorlesen/folge";
import { geraetDa, geraetestimmen, Geraetesprecher } from "../vorlesen/geraet";
import { medienAus, medienStand, zeigeMedien, type Werk } from "../vorlesen/mediensitzung";
import type { Lesequelle, Sprecher, Stimme, Strecke } from "../vorlesen/typen";
import { Vorlauf } from "../vorlesen/vorlauf";
import { anschluesse } from "./anschluesse.svelte";
import { melde } from "./meldungen.svelte";

const SCHLUESSEL = "vorlesen.stimme";
const SCHLUESSEL_TEMPO = "vorlesen.tempo";
const PROBE = "So klingt diese Stimme beim Vorlesen.";
const GRUPPEN = { eigene: "Eigene Stimmen", weitere: "Weitere Stimmen", eingebaut: "Eingebaute Stimmen" };
const OHNE_WERK: Werk = { titel: "", autor: "", bild: "" };
/** So oft sichert das laufende Vorlesen seine Stelle, falls das Fenster ohne Abschied zugeht */
const SICHERN_MS = 15_000;

export const TEMPI = [0.8, 0.9, 1, 1.1, 1.25, 1.5];

/** Ein einzelner Text, der nirgends mitläuft (Auswahl, Antwort, Probe) */
function textquelle(text: string, was: string): Lesequelle {
  return { anzahl: 1, name: () => was, text: async () => text, markiere: () => {}, fuehre: async () => {}, sichtbar: () => true, kapitelende: async () => null };
}

class Vorlesestand {
  aktiv = $state(false);
  wartet = $state(false);
  pausiert = $state(false);
  /** Von Hand weggeblättert: die gelesene Stelle ist nicht im Blick */
  weg = $state(false);
  was = $state("");
  einheit = $state(0);
  schlaf = $state<Schlaf>({ art: "aus" });
  quelle = $state.raw<Lesequelle | null>(null);
  kannVor = $state(false);
  #tempo = $state(TEMPI.includes(Number(gemerkt(SCHLUESSEL_TEMPO))) ? Number(gemerkt(SCHLUESSEL_TEMPO)) : 1);
  #gewaehlt = $state(gemerkt(SCHLUESSEL));
  #dienst = $state<Dienststimmen | null>(null);
  #geraet = $state<Stimme[]>([]);
  #gefragt = false;
  #sprecher: Record<string, Sprecher> = { dienst: new Dienstsprecher(), geraet: new Geraetesprecher() };
  #vorlauf = new Vorlauf();
  #folge: Vorlesefolge | null = null;
  #werk = OHNE_WERK;
  /** Buch, aus dem gelesen wird; null bei einzelnen Texten (Auswahl, Probe), die nichts merken */
  #buch: number | null = null;
  #gesichert = 0;
  /** Gemerkte Stelle eines Buchs, wie der Server sie kennt: "Weiterlesen" im Feld Vorlesen */
  gemerkt = $state.raw<{ buch: number; stelle: Vorlesestelle | null } | null>(null);

  constructor() {
    // Geht das Fenster zu (Tab zu, neu geladen), bleibt die Stelle so genau wie beim Anhalten
    if (typeof window !== "undefined") addEventListener("pagehide", () => this.#sichere());
  }

  stimmen = $derived<Stimme[]>(
    anschluesse.jetzt.vorlesen
      ? this.#dienst?.da
        ? [{ id: "dienst:", name: "Vorgabe des Sprechdienstes", gruppe: "Sprechdienst" }, ...this.#dienst.stimmen.map((s) => ({ id: `dienst:${s.id}`, name: s.name, gruppe: GRUPPEN[s.gruppe] }))]
        : []
      : this.#geraet,
  );

  /** Die Stimme, die gilt: die gewählte, solange es sie gibt, sonst die erste */
  stimme = $derived(this.stimmen.some((s) => s.id === this.#gewaehlt) ? this.#gewaehlt : (this.stimmen[0]?.id ?? ""));
  hinweis = $derived(this.#dienst?.hinweis ?? "");
  name = $derived(this.quelle?.name(this.einheit) ?? "");

  gruppen = $derived.by(() => {
    const aus = new Map<string, [string, string][]>();
    for (const s of this.stimmen) aus.set(s.gruppe, [...(aus.get(s.gruppe) ?? []), [s.id, s.name]]);
    return [...aus];
  });

  /** Einmal je Seite; die Stimmen des Geräts melden manche Browser erst später. */
  pruefe(): void {
    if (this.#gefragt) return;
    this.#gefragt = true;
    if (anschluesse.jetzt.vorlesen) {
      ladeDienststimmen().then((d) => (this.#dienst = d)).catch(() => (this.#gefragt = false));
      return;
    }
    if (!geraetDa()) return;
    this.#geraet = geraetestimmen();
    speechSynthesis.addEventListener?.("voiceschanged", () => (this.#geraet = geraetestimmen()));
  }

  waehle(id: string): void {
    this.#gewaehlt = id;
    merke(SCHLUESSEL, id);
    const [sprecher, stimme] = this.#teile();
    if (!sprecher) return this.halt();
    sprecher.tempo = this.#tempo;
    this.#folge?.wechsle(sprecher, stimme);
  }

  #teile(): [Sprecher | undefined, string] {
    const trenner = this.stimme.indexOf(":");
    return [this.#sprecher[this.stimme.slice(0, trenner)], this.stimme.slice(trenner + 1)];
  }

  get tempo(): number {
    return this.#tempo;
  }
  set tempo(wert: number) {
    this.#tempo = wert;
    merke(SCHLUESSEL_TEMPO, String(wert));
    for (const s of Object.values(this.#sprecher)) s.tempo = wert;
  }

  /** Noch im Tippen rufen, wenn der Text erst danach geholt wird. */
  entsperre(): void {
    this.#teile()[0]?.entsperre();
  }

  /** Ein einzelner Text */
  lies(text: string, was: string): void {
    if (text.trim()) this.liesBuch(textquelle(text.trim(), was), { von: { einheit: 0, zeichen: 0 }, bis: null }, was);
    else this.halt();
  }

  /** Die gemerkte Stelle eines Buchs vom Server; gilt auf jedem Gerät */
  async ladeStelle(buch: number): Promise<void> {
    try {
      const stelle = await holeVorlesestelle(buch);
      if (this.#buch !== buch || !this.aktiv) this.gemerkt = { buch, stelle };
    } catch {
      // ohne Antwort bleibt, was bekannt ist
    }
  }

  /** Eine Strecke eines Buchs; die Ansicht läuft mit. buch: aus diesem Buch, dann merkt der Server die Stelle */
  liesBuch(quelle: Lesequelle, strecke: Strecke, was: string, werk: Werk = OHNE_WERK, buch: number | null = null): void {
    // Wer liest, ohne dass jemand die Stimmen erfragt hat (etwa aus der Auswahl), fragt hier
    this.pruefe();
    this.halt();
    this.#buch = buch;
    this.#gesichert = Date.now();
    const [sprecher, stimme] = this.#teile();
    if (!sprecher) return void melde.warn(this.hinweis || "Hier gibt es keine Stimme zum Vorlesen");
    sprecher.tempo = this.#tempo;
    sprecher.entsperre();
    Object.assign(this, { aktiv: true, wartet: true, pausiert: false, weg: false, was, quelle, einheit: strecke.von.einheit });
    this.#werk = werk;
    const gilt = () => this.quelle === quelle;
    this.#folge = new Vorlesefolge(quelle, strecke, sprecher, stimme, this.#vorlauf, {
      zustand: (z) => gilt() && this.#zeige(z),
      ende: () => gilt() && this.#zuEnde(),
      gerissen: (grund) => {
        if (!gilt()) return;
        this.#sichere();
        melde.warn(`${grund}. Weiter setzt an derselben Stelle fort.`);
      },
      eingeschlafen: () => {
        if (!gilt()) return;
        this.schlaf = { art: "aus" };
        this.#sichere();
      },
    });
    this.#zeige({ wartet: true, pausiert: false, weg: false, einheit: strecke.von.einheit });
  }

  #zeige(z: { wartet: boolean; pausiert: boolean; weg: boolean; einheit: number }): void {
    const neu = z.einheit !== this.einheit || !navigator.mediaSession?.metadata;
    Object.assign(this, z);
    if (!z.pausiert && !z.wartet && Date.now() - this.#gesichert >= SICHERN_MS) this.#sichere();
    this.kannVor = this.#folge?.kannVor ?? false;
    if (neu) this.#zeigeMedien();
    medienStand(!z.pausiert);
  }

  #zeigeMedien(): void {
    zeigeMedien(this.#werk, this.name || this.was, {
      weiter: () => this.weiter(), pause: () => this.pausiere(), halt: () => this.halt(),
      satzZurueck: () => this.satzZurueck(), satzVor: () => this.satzVor(), einheitZurueck: () => this.einheitZurueck(), einheitVor: () => this.einheitVor(),
    });
  }

  probe(): void {
    this.lies(PROBE, "Probe");
  }

  pausiere(): void {
    this.#folge?.pausiere();
    this.#sichere();
  }
  weiter(): void {
    this.entsperre();
    this.#folge?.weiter();
  }
  pauseOderWeiter(): void {
    if (this.pausiert) this.weiter();
    else this.pausiere();
  }
  satzVor(): void {
    this.#folge?.satzVor();
  }
  satzZurueck(): void {
    this.#folge?.satzZurueck();
  }
  einheitVor(): void {
    this.#folge?.einheitVor();
  }
  einheitZurueck(): void {
    this.#folge?.einheitZurueck();
  }
  zurStelle(): void {
    void this.#folge?.zurStelle();
  }
  /** Die Ansicht des Buchs hat sich bewegt */
  bewegt(): void {
    this.#folge?.bewegt();
  }
  setzeSchlaf(schlaf: Schlaf): void {
    this.schlaf = schlaf;
    void this.#folge?.setzeSchlaf(schlaf);
  }

  /** Anhalten, auch beim Schließen des Buchs: die Stelle bleibt zum Weiterlesen */
  halt(): void {
    this.#sichere();
    this.#folge?.halt();
    this.#fertig();
  }

  /** Der gewählte Umfang ist zu Ende gelesen: nichts mehr zum Weiterlesen */
  #zuEnde(): void {
    const buch = this.#buch;
    if (buch !== null) {
      this.gemerkt = { buch, stelle: null };
      void vergissVorlesestelle(buch).catch(() => {});
    }
    this.#fertig();
  }

  /** Die Stelle des Satzes, der gerade klingt oder zuletzt klang, an den Server; ohne Netz bleibt sie hier bekannt */
  #sichere(): void {
    const [f, buch] = [this.#folge, this.#buch];
    if (!f || buch === null) return;
    this.#gesichert = Date.now();
    const { einheit, zeichen } = f.stelle;
    const neu = { einheit, zeichen, bis_einheit: f.bis?.einheit ?? null, bis_zeichen: f.bis?.zeichen ?? null, umfang: this.was, ort: f.quelle.name(einheit) };
    this.gemerkt = { buch, stelle: { ...neu, gemerkt_am: new Date().toISOString() } };
    void merkeVorlesestelle(buch, neu).catch(() => {});
  }

  #fertig(): void {
    this.#folge = null;
    this.#buch = null;
    Object.assign(this, { aktiv: false, wartet: false, pausiert: false, weg: false, was: "", quelle: null, kannVor: false, schlaf: { art: "aus" } });
    medienAus();
  }
}

export const vorlesen = new Vorlesestand();
