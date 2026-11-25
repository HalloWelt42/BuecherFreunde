// Nachschlagen im kleinen Fenster: Wort suchen, Artikel lesen, Verweisen folgen, zurück
import { ladeArtikel, sucheNach, type Nachschlagartikel, type Nachschlagtreffer } from "../api/helfer";

interface Schritt {
  buch: string;
  pfad: string;
  anker: string;
}

const WORT_HOECHSTENS = 120;

class Nachschlagstand {
  offen = $state(false);
  wort = $state("");
  treffer = $state.raw<Nachschlagtreffer[]>([]);
  artikel = $state.raw<Nachschlagartikel | null>(null);
  laedt = $state(false);
  fehler = $state("");
  #weg = $state.raw<Schritt[]>([]);
  #lauf = 0;

  kannZurueck = $derived(this.artikel !== null);

  /** Öffnet das Fenster zu einem gewählten Wort; trifft ein Titel genau, steht gleich sein Artikel da. */
  oeffne(wort: string): void {
    this.offen = true;
    const sauber = wort.replace(/\s+/g, " ").trim();
    void this.suche(sauber.length > WORT_HOECHSTENS ? sauber.slice(0, sauber.lastIndexOf(" ", WORT_HOECHSTENS)) : sauber, true);
  }

  schliesse(): void {
    this.offen = false;
  }

  async suche(wort: string, gleichLesen = false): Promise<void> {
    this.wort = wort;
    this.artikel = null;
    this.#weg = [];
    this.treffer = [];
    if (!wort.trim()) return;
    await this.#tue(async (gilt) => {
      const treffer = await sucheNach(wort.trim());
      if (!gilt()) return;
      this.treffer = treffer;
      const genau = treffer[0];
      if (gleichLesen && genau && genau.titel.toLocaleLowerCase("de") === wort.trim().toLocaleLowerCase("de")) await this.#hole(genau, gilt);
    });
  }

  lies(schritt: Schritt): Promise<void> {
    return this.#tue((gilt) => this.#hole(schritt, gilt));
  }

  /** Einen Schritt zurück, vom ersten Artikel zur Trefferliste */
  async zurueck(): Promise<void> {
    const vorher = this.#weg.at(-2);
    this.#weg = this.#weg.slice(0, -2);
    if (vorher) await this.lies(vorher);
    else this.artikel = null;
  }

  async #hole(s: Schritt, gilt: () => boolean): Promise<void> {
    const artikel = await ladeArtikel(s.buch, s.pfad, this.wort, s.anker);
    if (!gilt()) return;
    this.artikel = artikel;
    this.#weg = [...this.#weg, { buch: artikel.buch, pfad: artikel.pfad, anker: s.anker }];
  }

  /** Nur der jüngste Aufruf gilt; ein langsamer älterer überschreibt nichts. */
  async #tue(arbeit: (gilt: () => boolean) => Promise<void>): Promise<void> {
    const lauf = ++this.#lauf;
    const gilt = () => lauf === this.#lauf;
    this.laedt = true;
    this.fehler = "";
    try {
      await arbeit(gilt);
    } catch (e) {
      if (gilt()) this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      if (gilt()) this.laedt = false;
    }
  }
}

export const nachschlag = new Nachschlagstand();
