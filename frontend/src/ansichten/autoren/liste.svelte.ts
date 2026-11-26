// Autorenliste: bleibt stehen, wenn man von einer Autorenseite zurückkommt
import { autorenStatistik, holeAutoren, type Autor, type Autorenstatistik } from "../../lib/api/authors";
import { vergissRollstand } from "../../lib/rollstand";
import type { Filterziel } from "../../lib/stand/schnellfilter.svelte";

export type Autorsortierung = "name" | "buecher" | "datum";

export const autorsortierungen: [Autorsortierung, string, "asc" | "desc"][] = [["name", "Name", "asc"], ["buecher", "Bücher", "desc"], ["datum", "Datum", "desc"]];

const JE_SEITE = 36;

class Autorenansicht {
  autoren = $state<Autor[]>([]);
  gesamt = $state(0);
  suche = $state("");
  sortierung = $state<Autorsortierung>("name");
  richtung = $state<"asc" | "desc">("asc");
  laedt = $state(false);
  geladen = $state(false);
  fehler = $state("");
  statistik = $state<Autorenstatistik | null>(null);
  #seite = 0;
  #lauf = 0;

  #hole(seite: number) {
    return holeAutoren({ seite, pro_seite: JE_SEITE, suche: this.suche.trim() || undefined, sortierung: this.sortierung, richtung: this.richtung });
  }

  async laden(): Promise<void> {
    await this.#nimm(async () => {
      const a = await this.#hole(1);
      this.#seite = 1;
      return a;
    });
    void this.zaehlen();
  }

  /** Neues Suchwort: die Liste von vorn */
  filtere(wort: string): void {
    this.suche = wort;
    vergissRollstand("/authors");
    void this.laden();
  }

  async mehr(): Promise<void> {
    if (this.laedt || this.autoren.length >= this.gesamt) return;
    await this.#nimm(async () => {
      const seite = this.#seite + 1;
      const a = await this.#hole(seite);
      this.#seite = seite;
      const bekannt = new Set(this.autoren.map((x) => x.id));
      return { ...a, autoren: [...this.autoren, ...a.autoren.filter((x) => !bekannt.has(x.id))] };
    });
  }

  /** Denselben Ausschnitt neu holen, ohne nach oben zu springen */
  async auffrischen(): Promise<void> {
    const seiten = Math.max(1, this.#seite);
    await this.#nimm(async () => {
      const teile = await Promise.all(Array.from({ length: seiten }, (_, n) => this.#hole(n + 1)));
      return { ...teile[0], autoren: teile.flatMap((t) => t.autoren) };
    });
    void this.zaehlen();
  }

  async #nimm(hole: () => Promise<{ autoren: Autor[]; gesamt: number }>): Promise<void> {
    const lauf = ++this.#lauf;
    this.laedt = true;
    this.fehler = "";
    try {
      const a = await hole();
      if (lauf !== this.#lauf) return;
      this.autoren = a.autoren;
      this.gesamt = a.gesamt;
    } catch (e) {
      if (lauf === this.#lauf) this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      if (lauf === this.#lauf) {
        this.laedt = false;
        this.geladen = true;
      }
    }
  }

  async zaehlen(): Promise<void> {
    try {
      this.statistik = await autorenStatistik();
    } catch {
      this.statistik = null;
    }
  }

  /** Dieselbe Sortierung noch einmal dreht die Richtung */
  sortiere(nach: Autorsortierung): void {
    if (nach === this.sortierung) this.richtung = this.richtung === "asc" ? "desc" : "asc";
    else {
      this.sortierung = nach;
      this.richtung = autorsortierungen.find(([s]) => s === nach)![2];
    }
    void this.laden();
  }
}

export const autorenansicht = new Autorenansicht();

/** Als Schnellfilter grenzt das Suchfeld die Autoren nach dem Namen ein, über die Suche der Liste */
export const autorenfilter: Filterziel = {
  get wort() {
    return autorenansicht.suche.trim();
  },
  hinweis: "Name",
  get treffer() {
    return autorenansicht.geladen ? autorenansicht.gesamt : null;
  },
  get gesamt() {
    return autorenansicht.statistik?.gesamt ?? null;
  },
  filtere: (wort) => autorenansicht.filtere(wort),
};
