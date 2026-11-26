// Der Stand des Kinderlesers: welche Einheit und Seite gezeigt wird, die Lesezeile, das eine Lesezeichen, und beim Vorlesen
// der Satz und das Wort, das gerade klingt. Die Seiten entstehen aus dem Maß der Fläche (lib/kind/seiten.ts); ändert es sich,
// bleibt die Stelle, an der man liest. Vorgelesen wird mit dem Vorlesen der App (lib/stand/vorlesen.svelte.ts) über eine
// Lesequelle, die hier mitläuft und am Ende einer Seite weiterblättert.
import type { Lesequelle, Satzort, Stelle } from "../vorlesen/typen";
import type { Kinderquelle } from "./inhalt";
import { geschaetztesWort, wortBei, woerterIm } from "./mitlesen";
import { seiteBei, seitenAus, woerterDer, type Kinderseite, type Seitenmass } from "./seiten";
import type { Einheit, Kinderstelle, Wort } from "./typen";

export interface Lesergriffe {
  /** Ist die Lesezeit um oder Ruhezeit? Dann wird nicht mehr weitergeblättert. */
  ruheFaellig(): boolean;
  /** Die Seite ist zu Ende und die Ruhe fällig */
  ruhe(): void;
  /** Die Stelle hat sich geändert */
  gerueckt(stelle: Kinderstelle): void;
  /** Liefert die Stimme die Lage jedes Wortes? Sonst wird im Satz geschätzt. */
  wortgenau(): boolean;
}

const leer = (s: Kinderseite[]) => s.length === 1 && !s[0].bild && !s[0].zeilen.length;

export class Kinderlesestand {
  einheit = $state(0);
  seite = $state(0);
  seiten = $state.raw<Kinderseite[]>([]);
  laedt = $state(true);
  fehler = $state("");
  amEnde = $state(false);
  /** Die Zeile der Lesezeile auf der Seite */
  zeile = $state(0);
  /** Was gerade vorgelesen wird */
  satz = $state.raw<Satzort | null>(null);
  /** Anfang des Wortes, das gerade klingt; -1: keins */
  wort = $state(-1);
  lesezeichen = $state.raw<Kinderstelle | null>(null);

  jetzt = $derived<Kinderseite | null>(this.seiten[this.seite] ?? null);
  stelle = $derived<Kinderstelle>({ einheit: this.einheit, zeichen: this.jetzt?.von ?? 0 });
  aufLesezeichen = $derived(!!this.lesezeichen && !!this.jetzt && this.lesezeichen.einheit === this.einheit && this.lesezeichen.zeichen >= this.jetzt.von && this.lesezeichen.zeichen < Math.max(this.jetzt.bis, this.jetzt.von + 1));
  istErste = $derived(this.einheit === 0 && this.seite === 0);

  #einheiten = new Map<number, Einheit>();
  #seitenJe = new Map<number, Kinderseite[]>();
  #mass: Seitenmass | null = null;
  #ziel: Kinderstelle = { einheit: 0, zeichen: 0 };
  #lauf = 0;

  constructor(readonly quelle: Kinderquelle, private griffe: Lesergriffe) {}

  /** Beginnt an einer Stelle; gezeigt wird, sobald das Maß der Fläche bekannt ist */
  async beginne(stelle: Kinderstelle, lesezeichen: Kinderstelle | null): Promise<void> {
    this.lesezeichen = lesezeichen;
    this.#ziel = { einheit: Math.min(Math.max(0, stelle.einheit), this.quelle.anzahl - 1), zeichen: Math.max(0, stelle.zeichen) };
    if (this.#mass) await this.zeige(this.#ziel);
  }

  /** Neues Maß (Größe, Schrift, Drehen): neu umbrechen, die Stelle bleibt */
  async setzeMass(m: Seitenmass): Promise<void> {
    const ziel = this.jetzt ? this.stelle : this.#ziel;
    this.#mass = m;
    this.#seitenJe.clear();
    await this.zeige(ziel);
  }

  async #einheit(nr: number): Promise<Einheit> {
    let e = this.#einheiten.get(nr);
    if (!e) {
      e = await this.quelle.einheit(nr);
      this.#einheiten.set(nr, e);
    }
    return e;
  }

  async #seiten(nr: number): Promise<Kinderseite[]> {
    let s = this.#seitenJe.get(nr);
    if (!s) {
      const e = await this.#einheit(nr);
      s = seitenAus(nr, e.bloecke, this.#mass!);
      this.#seitenJe.set(nr, s);
    }
    return s;
  }

  /** Die Seite mit dieser Stelle zeigen; vorwärts: über leere Einheiten hinweg in diese Richtung */
  async zeige(stelle: Kinderstelle, richtung: 1 | -1 = 1, amSchluss = false): Promise<void> {
    if (!this.#mass) {
      this.#ziel = stelle;
      return;
    }
    const lauf = ++this.#lauf;
    this.fehler = "";
    try {
      let nr = stelle.einheit;
      let seiten = await this.#seiten(nr);
      while (leer(seiten) && nr + richtung >= 0 && nr + richtung < this.quelle.anzahl) {
        nr += richtung;
        seiten = await this.#seiten(nr);
      }
      if (lauf !== this.#lauf) return;
      this.einheit = nr;
      this.seiten = seiten;
      this.seite = amSchluss ? seiten.length - 1 : nr === stelle.einheit ? seiteBei(seiten, stelle.zeichen) : 0;
      this.amEnde = false;
      this.zeile = 0;
      this.griffe.gerueckt(this.stelle);
      void this.#vorhalten(nr + 1);
    } catch (e) {
      if (lauf === this.#lauf) this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      if (lauf === this.#lauf) this.laedt = false;
    }
  }

  /** Die nächste Einheit liegt schon bereit, wenn geblättert wird */
  async #vorhalten(nr: number): Promise<void> {
    if (nr < this.quelle.anzahl) await this.#seiten(nr).catch(() => undefined);
  }

  /** Eine Seite weiter; am Ende des Buchs der Schluss. Ist die Ruhe fällig, kommt sie statt der nächsten Seite. */
  async weiter(): Promise<void> {
    if (this.griffe.ruheFaellig()) return this.griffe.ruhe();
    if (this.amEnde) return;
    if (this.seite + 1 < this.seiten.length) {
      this.seite++;
      this.zeile = 0;
      this.griffe.gerueckt(this.stelle);
      return;
    }
    if (this.einheit + 1 >= this.quelle.anzahl) {
      this.amEnde = true;
      return;
    }
    await this.zeige({ einheit: this.einheit + 1, zeichen: 0 }, 1);
  }

  async zurueck(): Promise<void> {
    if (this.amEnde) {
      this.amEnde = false;
      return;
    }
    if (this.seite > 0) {
      this.seite--;
      this.zeile = 0;
      this.griffe.gerueckt(this.stelle);
      return;
    }
    if (this.einheit > 0) await this.zeige({ einheit: this.einheit - 1, zeichen: 0 }, -1, true);
  }

  // Lesezeile

  get zeilenzahl(): number {
    return this.jetzt?.zeilen.length ?? 0;
  }

  setzeZeile(nr: number): void {
    this.zeile = Math.max(0, Math.min(this.zeilenzahl - 1, nr));
  }

  /** Tippen auf eine Zeile: sie wird die Lesezeile; auf die Lesezeile: die nächste */
  tippeZeile(nr: number): void {
    this.setzeZeile(nr === this.zeile ? nr + 1 : nr);
  }

  // Lesezeichen

  /** Setzt das eine Lesezeichen auf diese Seite oder nimmt es von ihr */
  lesezeichenUmschalten(): Kinderstelle | null {
    this.lesezeichen = this.aufLesezeichen ? null : { ...this.stelle };
    this.griffe.gerueckt(this.stelle);
    return this.lesezeichen;
  }

  async zumLesezeichen(): Promise<void> {
    if (this.lesezeichen) await this.zeige(this.lesezeichen);
  }

  // Vorlesen und Mitlesen

  /** Die Wörter der gezeigten Einheit */
  #woerter(): Wort[] {
    return (this.#einheiten.get(this.einheit)?.bloecke ?? []).flatMap((b) => (b.art === "bild" ? [] : b.woerter));
  }

  sichtbar(ort: Satzort): boolean {
    const s = this.jetzt;
    return !!s && ort.einheit === this.einheit && ort.von < Math.max(s.bis, s.von + 1) && ort.bis > s.von;
  }

  /** Wo das Vorlesen beginnt: an der Lesezeile, sonst am Anfang der Seite */
  vorleseanfang(mitZeile: boolean): Stelle {
    const z = mitZeile ? this.jetzt?.zeilen[this.zeile]?.woerter[0] : undefined;
    return { einheit: this.einheit, zeichen: z?.von ?? this.jetzt?.von ?? 0 };
  }

  #markiere(ort: Satzort | null): void {
    this.satz = ort;
    if (!ort) this.wort = -1;
  }

  async #fuehre(stelle: Stelle): Promise<void> {
    const s = this.jetzt;
    const weg = !s || stelle.einheit !== this.einheit || stelle.zeichen >= Math.max(s.bis, s.von + 1) || stelle.zeichen < s.von;
    if (weg) {
      // Am Ende der Seite: ist die Ruhe fällig, endet es hier
      if (this.griffe.ruheFaellig()) return this.griffe.ruhe();
      await this.zeige(stelle);
    }
    const satz = this.satz;
    const woerter = this.#woerter();
    let i: number;
    if (this.griffe.wortgenau() || !satz || satz.einheit !== stelle.einheit) i = wortBei(woerter, stelle.zeichen);
    else {
      const imSatz = woerterIm(woerter, satz.von, satz.bis);
      const anteil = (stelle.zeichen - satz.von) / Math.max(1, satz.bis - satz.von);
      const w = imSatz[geschaetztesWort(imSatz, anteil)];
      i = w ? woerter.indexOf(w) : wortBei(woerter, stelle.zeichen);
    }
    this.wort = woerter[i]?.von ?? -1;
    // Die Lesezeile geht mit
    const zeilen = this.jetzt?.zeilen ?? [];
    const z = zeilen.findIndex((zeile) => zeile.woerter.some((w) => w.von === this.wort));
    if (z >= 0) this.zeile = z;
  }

  /** Die Lesequelle für das Vorlesen der App */
  vorlesequelle(): Lesequelle {
    return {
      anzahl: this.quelle.anzahl,
      name: (e) => this.quelle.name(e),
      text: async (e) => (await this.#einheit(e)).text,
      markiere: (ort) => this.#markiere(ort),
      fuehre: (stelle) => this.#fuehre(stelle),
      sichtbar: (ort) => this.sichtbar(ort),
      kapitelende: async () => null,
    };
  }

  /** Die Wörter der gezeigten Seite, für die Ansicht */
  get woerterDerSeite(): Wort[] {
    return this.jetzt ? woerterDer(this.jetzt) : [];
  }
}
