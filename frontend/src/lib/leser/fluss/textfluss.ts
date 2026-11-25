// Die gemeinsame Schicht aller Textleser (PDF als Text, MD, TXT): hält den Lesefluss der gewählten Art, baut ihn beim
// Wechsel um und bricht neu um, wenn sich Fläche, Schrift, Bilder oder der Text selbst ändern. Die Stelle bleibt stehen.
import { Blaetterfluss, CssSpalten } from "./blaettern";
import type { Leseart, Lesefluss, Ziel } from "./fluss";
import { DomScrollflaeche, Scrollfluss } from "./scrollen";
import { messeImFenster, Textmass, type Anker } from "./textmass";

export interface Textteile {
  /** Der sichtbare Ausschnitt */
  flaeche: HTMLElement;
  /** Das Papier darin */
  blatt: HTMLElement;
  /** Der Text auf dem Papier */
  satz: HTMLElement;
}

const KLASSE = "schirmweise";

export class Textfluss {
  #spalten: CssSpalten;
  #scroll: DomScrollflaeche;
  #mass: Textmass;
  #fluss: Lesefluss;
  #bild = 0;
  #loesen: (() => void)[] = [];

  constructor(private teile: Textteile, art: Leseart, private bewegt: () => void) {
    this.#spalten = new CssSpalten(teile.blatt, teile.satz);
    this.#scroll = new DomScrollflaeche(teile.flaeche);
    this.#mass = new Textmass(teile.satz, (a) => {
      const r = messeImFenster(a);
      return r && (this.art === "blaettern" ? this.#spalten.imSatz(r) : this.#scroll.imInhalt(r));
    });
    this.#fluss = this.#baue(art);
    this.#beobachte();
  }

  get art(): Leseart {
    return this.teile.flaeche.classList.contains(KLASSE) ? "blaettern" : "scrollen";
  }
  get anteil(): number {
    return this.#fluss.anteil;
  }
  get amAnfang(): boolean {
    return this.#fluss.amAnfang;
  }
  get amEnde(): boolean {
    return this.#fluss.amEnde;
  }

  get davor(): number {
    return this.#fluss.davor;
  }
  get danach(): number {
    return this.#fluss.danach;
  }

  vor = (): boolean => this.#fluss.vor();
  zurueck = (): boolean => this.#fluss.zurueck();
  zuAnteil = (anteil: number): void => this.#fluss.zuAnteil(anteil);
  zu = (ziel: Ziel): void => this.#fluss.zu(ziel);
  halt = (): Anker | null => this.#fluss.halt();
  erreicht = (e: Element): boolean => this.#fluss.erreicht(e);

  /** Anteil einer Stelle am ganzen Text, etwa für eine Markierung */
  anteilVon(knoten: Node, versatz: number): number {
    return this.#mass.anteil(knoten.nodeType === Node.TEXT_NODE ? { knoten, versatz } : { knoten: knoten.childNodes[versatz] ?? knoten, versatz: 0 });
  }

  /** Wechsel der Art: dieselbe Stelle steht danach oben */
  setzeArt(art: Leseart): void {
    if (art === this.art) return;
    const halt = this.#fluss.amAnfang ? null : this.#fluss.halt();
    this.#fluss.zerstoere();
    this.#fluss = this.#baue(art);
    if (halt) this.#fluss.zu(halt);
    else this.#fluss.zuAnteil(0);
  }

  /** Umbau des Textes, bei dem die Stelle stehen bleibt (nachladen, andere Schrift) */
  async halte(tun: () => unknown): Promise<void> {
    this.#fluss.halteFest();
    await tun();
    this.#mass.veraltet();
    this.#fluss.neu();
  }

  neu = (): void => this.#fluss.neu();

  zerstoere(): void {
    cancelAnimationFrame(this.#bild);
    for (const l of this.#loesen) l();
    this.#fluss.zerstoere();
    this.#mass.zerstoere();
  }

  #baue(art: Leseart): Lesefluss {
    this.teile.flaeche.classList.toggle(KLASSE, art === "blaettern");
    if (art === "blaettern") {
      this.teile.flaeche.scrollTop = 0;
      return new Blaetterfluss(this.#spalten, this.#mass, this.bewegt);
    }
    this.#spalten.raeume();
    return new Scrollfluss(this.#scroll, this.#mass, this.bewegt);
  }

  // Alles, was den Umbruch ändert, einmal je Bild
  #beobachte(): void {
    const spaeter = () => {
      cancelAnimationFrame(this.#bild);
      this.#bild = requestAnimationFrame(() => this.#fluss.neu());
    };
    const groesse = new ResizeObserver(spaeter);
    groesse.observe(this.teile.blatt);
    const umbau = new MutationObserver(spaeter);
    umbau.observe(this.teile.satz, { childList: true, subtree: true, characterData: true });
    // Bilder melden sich nur selbst, ihr Ereignis steigt nicht auf
    this.teile.satz.addEventListener("load", spaeter, true);
    document.fonts?.addEventListener("loadingdone", spaeter);
    // Mit der Tastatur in einen Verweis auf einem anderen Schirm: dorthin blättern
    const fokus = (e: FocusEvent) => {
      if (this.art === "blaettern" && e.target instanceof Element && e.target.matches(":focus-visible")) this.#fluss.zu(e.target);
    };
    this.teile.satz.addEventListener("focusin", fokus);
    this.#loesen = [
      () => groesse.disconnect(),
      () => umbau.disconnect(),
      () => this.teile.satz.removeEventListener("load", spaeter, true),
      () => document.fonts?.removeEventListener("loadingdone", spaeter),
      () => this.teile.satz.removeEventListener("focusin", fokus),
    ];
  }
}
