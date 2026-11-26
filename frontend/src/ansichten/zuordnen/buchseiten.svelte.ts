// Eine Bücherliste der Zuordnung (BF-67): seitenweise vom Server oder ganz, mit Änderungen an Ort und Stelle
import { listeBooks } from "../../lib/api/books";
import type { Parameter } from "../../lib/api/client";
import type { Buch, BuchListe } from "../../lib/typen";

const JE_SEITE = 100;

export class Buchseiten {
  liste = $state<Buch[]>([]);
  gesamt = $state(0);
  laedt = $state(false);
  fehler = $state("");
  geladen = $state(false);
  /** Alle Seiten auf einmal: eine Sammlung braucht für die Reihenfolge jeden Band */
  readonly ganz: boolean;
  #filter: Parameter = {};
  #seite = 0;
  #lauf = 0;

  constructor(ganz = false) {
    this.ganz = ganz;
  }

  laden(filter: Parameter): Promise<void> {
    this.#filter = filter;
    return this.#vonVorn(this.ganz ? Infinity : 1);
  }

  mehr(): Promise<void> {
    if (this.laedt || this.liste.length >= this.gesamt) return Promise.resolve();
    const seite = this.#seite + 1;
    return this.#hole(async () => ({ teile: [await this.#holeSeite(seite)], seite, anhaengen: true }));
  }

  /** Dieselben Seiten noch einmal, etwa nach einer Änderung (Bandnummern vergibt der Server) */
  auffrischen(): Promise<void> {
    return this.#vonVorn(this.ganz ? Infinity : Math.max(1, this.#seite));
  }

  /** Bücher verlassen die Liste, ohne sie neu zu laden */
  nimm(ids: number[]): void {
    const weg = new Set(ids);
    const vorher = this.liste.length;
    this.liste = this.liste.filter((b) => !weg.has(b.id));
    this.gesamt = Math.max(0, this.gesamt - (vorher - this.liste.length));
  }

  /** Bücher kommen dazu (vorn), ohne Doppel */
  stelle(buecher: Buch[]): void {
    const da = new Set(this.liste.map((b) => b.id));
    const neu = buecher.filter((b) => !da.has(b.id));
    this.liste = [...neu, ...this.liste];
    this.gesamt += neu.length;
  }

  /** Eine neue Folge derselben und neuer Bücher; neue zählen mit */
  ordne(buecher: Buch[]): void {
    this.gesamt += buecher.length - this.liste.length;
    this.liste = buecher;
  }

  #holeSeite(seite: number): Promise<BuchListe> {
    return listeBooks({ ...this.#filter, seite, pro_seite: JE_SEITE });
  }

  /** Die Seiten 1 bis `bis` (Infinity: alle) */
  #vonVorn(bis: number): Promise<void> {
    return this.#hole(async () => {
      const erste = await this.#holeSeite(1);
      const seiten = Math.max(1, Math.min(bis, erste.seiten_gesamt));
      const weitere = await Promise.all(Array.from({ length: seiten - 1 }, (_, n) => this.#holeSeite(n + 2)));
      return { teile: [erste, ...weitere], seite: seiten, anhaengen: false };
    });
  }

  async #hole(tun: () => Promise<{ teile: BuchListe[]; seite: number; anhaengen: boolean }>): Promise<void> {
    const lauf = ++this.#lauf;
    this.laedt = true;
    this.fehler = "";
    try {
      const { teile, seite, anhaengen } = await tun();
      if (lauf !== this.#lauf) return;
      const buecher = teile.flatMap((t) => t.buecher);
      const da = new Set(anhaengen ? this.liste.map((b) => b.id) : []);
      this.liste = anhaengen ? [...this.liste, ...buecher.filter((b) => !da.has(b.id))] : buecher;
      this.gesamt = teile[0].gesamt;
      this.#seite = seite;
    } catch (e) {
      if (lauf === this.#lauf) this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      if (lauf === this.#lauf) {
        this.laedt = false;
        this.geladen = true;
      }
    }
  }
}
