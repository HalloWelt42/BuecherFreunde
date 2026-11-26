// Eine Vorlesefolge spielt eine Strecke einer Lesequelle Satz für Satz, führt die Ansicht mit und lässt sich steuern. Wer
// selbst weggeblättert hat, wird nicht zurückgezogen.
import { saetzeMitLage } from "./saetze";
import type { Lesequelle, Satzort, Sprecher, Stelle, Strecke } from "./typen";
import type { Vorlauf } from "./vorlauf";
import { Zulauf, type Posten } from "./zulauf";

export interface Folgegriffe {
  /** Wartet auf Ton, steht still, ist weggeblättert, welche Einheit */
  zustand(z: { wartet: boolean; pausiert: boolean; weg: boolean; einheit: number }): void;
  ende(): void;
  /** Der Ton blieb aus; die Folge steht still und lässt sich fortsetzen */
  gerissen(grund: string): void;
  /** Die Schlafuhr hat angehalten */
  eingeschlafen(): void;
}

export type Schlaf = { art: "aus" } | { art: "einheit" } | { art: "kapitel" } | { art: "minuten"; minuten: number };

type Befehl = "" | "vor" | "neu" | "zurueck";

const VERLAUF = 30;
/** Ist so viel vom Satz gesprochen, beginnt "Satz zurück" ihn neu, statt zum vorigen zu gehen */
const NEU_AB_S = 1.5;

export class Vorlesefolge {
  #zulauf: Zulauf;
  #verlauf: Posten[] = [];
  #jetzt: Posten | null = null;
  #letzter: Satzort | null = null;
  #anteil = 0;
  #lauf = 0;
  #befehl: Befehl = "";
  #weck: (() => void) | null = null;
  #wartet = true;
  #pausiert = false;
  #weg = false;
  #fuehrt = 0;
  #klang = false;
  #gerissen = false;
  #schlaf: Schlaf = { art: "aus" };
  #schlafGrenze: Stelle | null = null;
  #schlafUm = 0;

  constructor(readonly quelle: Lesequelle, private strecke: Strecke, private sprecher: Sprecher, private stimme: string, private vorlauf: Vorlauf, private griffe: Folgegriffe, private warte?: (ms: number) => Promise<unknown>) {
    this.#zulauf = this.#baue(strecke);
    this.vorlauf.beginnen();
    this.#melde();
    void this.#spiele();
  }

  get einheit(): number {
    return (this.#jetzt?.ort ?? this.#letzter)?.einheit ?? this.strecke.von.einheit;
  }
  /** Anfang des Satzes, der gerade klingt oder zuletzt klang; dort fängt ein späteres Weiterlesen an */
  get stelle(): Stelle {
    const ort = this.#jetzt?.ort ?? this.#letzter;
    return ort ? { einheit: ort.einheit, zeichen: ort.von } : this.strecke.von;
  }
  /** Ende des gewählten Umfangs; null: bis zum Ende des Buchs */
  get bis(): Stelle | null {
    return this.strecke.bis;
  }
  get kannVor(): boolean {
    return this.einheit + 1 < this.quelle.anzahl && (!this.strecke.bis || this.einheit < this.strecke.bis.einheit - (this.strecke.bis.zeichen > 0 ? 0 : 1));
  }

  #baue(strecke: Strecke): Zulauf {
    return new Zulauf(this.quelle, strecke, this.sprecher, this.stimme, () => this.#weck?.(), this.warte);
  }

  #melde(): void {
    this.griffe.zustand({ wartet: this.#wartet, pausiert: this.#pausiert, weg: this.#weg, einheit: this.einheit });
  }

  // Spielen

  async #spiele(): Promise<void> {
    const lauf = ++this.#lauf;
    for (;;) {
      const p = await this.#naechster(lauf);
      if (lauf !== this.#lauf) return;
      if (!p) return this.#beende();
      if (this.#sollSchlafen(p)) {
        this.#zulauf.lege(p);
        this.#legeSchlafen();
        continue;
      }
      this.#beginne(p);
      if (this.#pausiert && !(await this.#ruhe(lauf))) return;
      try {
        if (!this.#befehl) await this.sprecher.spiele(p.satz, this.stimme, (a) => this.#fortschritt(p, a));
      } catch (e) {
        if (lauf !== this.#lauf) return;
        this.#zulauf.lege(p);
        this.#reisse(e instanceof Error ? e.message : String(e));
        continue;
      }
      if (lauf !== this.#lauf) return;
      this.#nach(p);
    }
  }

  // Pausiert zwischen zwei Sätzen: warten, bis es weitergeht oder ein Befehl kommt
  async #ruhe(lauf: number): Promise<boolean> {
    while (this.#pausiert && !this.#befehl && lauf === this.#lauf) await this.#schlummer();
    return lauf === this.#lauf;
  }

  #schlummer(): Promise<void> {
    return new Promise((r) => (this.#weck = r));
  }

  #nach(p: Posten): void {
    const befehl = this.#befehl;
    this.#befehl = "";
    this.#jetzt = null;
    this.#letzter = p.ort;
    if (befehl === "neu") this.#zulauf.lege(p);
    else if (befehl === "zurueck") this.#zurueckVon(p);
    else {
      this.#verlauf.push(p);
      // Alter Ton braucht Platz und kommt nicht wieder
      if (this.#verlauf.length > VERLAUF) this.#verlauf.shift();
    }
  }

  #zurueckVon(p: Posten): void {
    const voriger = this.#verlauf.pop();
    if (voriger) this.#zulauf.lege(voriger, p);
    else void this.#vorigerSatz(p.ort).then((s) => this.#neuAb(s));
  }

  // Der Satz davor aus dem Text, wenn sein Ton nicht mehr da ist
  async #vorigerSatz({ einheit, von }: Satzort): Promise<Stelle> {
    const satz = saetzeMitLage((await this.quelle.text(einheit)).slice(0, von)).at(-1);
    if (satz) return { einheit, zeichen: satz.von };
    if (einheit === 0) return { einheit, zeichen: 0 };
    const davor = saetzeMitLage(await this.quelle.text(einheit - 1)).at(-1);
    return { einheit: einheit - 1, zeichen: davor?.von ?? 0 };
  }

  async #naechster(lauf: number): Promise<Posten | null> {
    let wartete = this.#wartet;
    for (;;) {
      if (lauf !== this.#lauf) return null;
      const z = this.#zulauf;
      const amEnde = z.fertig || !!z.fehler;
      if (!z.leer && (!wartete || this.vorlauf.genug(z.sekunden, amEnde))) {
        if (this.#wartet) {
          this.#wartet = false;
          this.#melde();
        }
        this.#klang = true;
        return z.nimm()!;
      }
      if (z.leer && z.fehler) {
        this.#reisse(z.fehler.message);
        await this.#ruhe(lauf);
        wartete = true;
        continue;
      }
      if (z.leer && z.fertig) return null;
      if (!wartete && this.#klang) this.vorlauf.abgerissen();
      wartete = true;
      if (!this.#wartet) {
        this.#wartet = true;
        this.#melde();
      }
      await this.#schlummer();
    }
  }

  #beende(): void {
    this.#lauf++;
    this.vorlauf.beenden();
    this.quelle.markiere(null);
    this.griffe.ende();
  }

  #reisse(grund: string): void {
    this.#gerissen = true;
    this.#pausiert = true;
    this.#wartet = false;
    this.#melde();
    this.griffe.gerissen(grund);
  }

  // Ansicht

  #beginne(p: Posten): void {
    const erster = !this.#letzter;
    this.#weg = !erster && !this.quelle.sichtbar(this.#letzter!);
    this.#jetzt = p;
    this.#anteil = 0;
    this.quelle.markiere(p.ort);
    this.#melde();
    // Der erste Satz kann auf dem Schirm davor beginnen: gezeigt wird ab der Stelle, an der man anfing
    const ab = erster && p.ort.einheit === this.strecke.von.einheit ? Math.min(p.ort.bis - 1, Math.max(p.ort.von, this.strecke.von.zeichen)) : p.ort.von;
    if (!this.#weg) void this.#fuehre({ einheit: p.ort.einheit, zeichen: ab }, erster);
  }

  #fortschritt(p: Posten, anteil: number): void {
    if (this.#jetzt !== p) return;
    this.#anteil = anteil;
    if (!this.#weg && !this.#fuehrt) void this.#fuehre({ einheit: p.ort.einheit, zeichen: Math.min(p.ort.bis - 1, Math.floor(p.ort.von + anteil * (p.ort.bis - p.ort.von))) }, false);
  }

  async #fuehre(stelle: Stelle, sofort: boolean): Promise<void> {
    this.#fuehrt++;
    try {
      await this.quelle.fuehre(stelle, sofort);
    } finally {
      this.#fuehrt--;
    }
  }

  /** Die Ansicht hat sich bewegt: ist die gelesene Stelle noch im Blick? */
  bewegt(): void {
    const ort = this.#jetzt?.ort ?? this.#letzter;
    if (!ort || this.#fuehrt) return;
    const weg = !this.quelle.sichtbar(ort);
    if (weg === this.#weg) return;
    this.#weg = weg;
    this.#melde();
  }

  async zurStelle(): Promise<void> {
    const ort = this.#jetzt?.ort ?? this.#letzter;
    if (!ort) return;
    this.#weg = false;
    this.#melde();
    await this.#fuehre({ einheit: ort.einheit, zeichen: ort.von }, true);
    this.quelle.markiere(ort);
  }

  // Steuern

  pausiere(): void {
    if (this.#pausiert) return;
    this.#pausiert = true;
    this.sprecher.pause();
    this.#melde();
  }

  weiter(): void {
    if (!this.#pausiert) return;
    this.#pausiert = false;
    if (this.#gerissen) {
      // Was noch bereitliegt, gehört zu einem Zulauf, der nicht mehr läuft: ab der nächsten Stelle neu holen
      this.#gerissen = false;
      const p = this.#zulauf.nimm();
      return this.#neuAb(p ? { einheit: p.ort.einheit, zeichen: p.ort.von } : this.#zulauf.bis);
    }
    this.sprecher.weiter();
    this.#melde();
    this.#weck?.();
  }

  satzVor(): void {
    this.#gib("vor");
  }

  satzZurueck(): void {
    if (this.#jetzt) return this.#gib(this.#anteil * this.#jetzt.satz.dauer > NEU_AB_S ? "neu" : "zurueck");
    const p = this.#verlauf.pop();
    if (p) this.#neuAb({ einheit: p.ort.einheit, zeichen: p.ort.von });
  }

  #gib(befehl: Befehl): void {
    if (!this.#jetzt) return;
    this.#befehl = befehl;
    this.sprecher.halt();
    this.#weck?.();
  }

  einheitVor(): void {
    if (this.kannVor) this.#neuAb({ einheit: this.einheit + 1, zeichen: 0 });
  }

  /** Erst an den Anfang dieser Einheit, dann in die vorige */
  einheitZurueck(): void {
    const ort = this.#jetzt?.ort ?? this.#letzter;
    const amAnfang = !ort || ort.von <= (ort.einheit === this.strecke.von.einheit ? this.strecke.von.zeichen : 0) + 1;
    this.#neuAb({ einheit: Math.max(0, this.einheit - (amAnfang ? 1 : 0)), zeichen: 0 });
  }

  /** Andere Stimme ab diesem Satz */
  wechsle(sprecher: Sprecher, stimme: string): void {
    this.sprecher.halt();
    [this.sprecher, this.stimme] = [sprecher, stimme];
    const ort = this.#jetzt?.ort ?? this.#letzter;
    this.#neuAb(ort ? { einheit: ort.einheit, zeichen: ort.von } : this.strecke.von);
  }

  #neuAb(stelle: Stelle): void {
    this.#lauf++;
    this.#zulauf.stoppe();
    this.sprecher.halt();
    this.#verlauf = [];
    this.#jetzt = null;
    this.#befehl = "";
    this.#wartet = true;
    this.#klang = false;
    this.#gerissen = false;
    this.strecke = { von: stelle, bis: this.strecke.bis };
    // Wer springt, will es auch sehen
    if (!this.#weg) this.#letzter = null;
    this.#zulauf = this.#baue(this.strecke);
    this.vorlauf.beginnen();
    this.#melde();
    this.#weck?.();
    void this.#spiele();
  }

  halt(): void {
    this.#lauf++;
    this.#zulauf.stoppe();
    this.sprecher.halt();
    this.quelle.markiere(null);
    this.#weck?.();
  }

  // Schlafuhr

  async setzeSchlaf(schlaf: Schlaf): Promise<void> {
    this.#schlaf = schlaf;
    this.#schlafGrenze = null;
    this.#schlafUm = schlaf.art === "minuten" ? Date.now() + schlaf.minuten * 60_000 : 0;
    const ort = this.#jetzt?.ort ?? this.#letzter;
    const stelle = { einheit: this.einheit, zeichen: ort?.von ?? 0 };
    if (schlaf.art === "einheit") this.#schlafGrenze = { einheit: stelle.einheit + 1, zeichen: 0 };
    if (schlaf.art === "kapitel") this.#schlafGrenze = await this.quelle.kapitelende(stelle);
  }

  #sollSchlafen({ ort }: Posten): boolean {
    if (this.#schlaf.art === "minuten") return Date.now() >= this.#schlafUm;
    const g = this.#schlafGrenze;
    return !!g && (ort.einheit > g.einheit || (ort.einheit === g.einheit && ort.von >= g.zeichen));
  }

  #legeSchlafen(): void {
    this.#schlaf = { art: "aus" };
    this.#schlafGrenze = null;
    this.#pausiert = true;
    this.#melde();
    this.griffe.eingeschlafen();
  }
}
