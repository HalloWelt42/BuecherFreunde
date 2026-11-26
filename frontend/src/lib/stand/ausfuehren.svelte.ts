// Ausführen (BF-29): welche Listings im Fenster offen sind und die Kopien je Buch und Stelle. Der Zustand liegt außerhalb
// des Lesers wie das Fenster in der Schale: Blättern, Suchsprünge, Wechsel zwischen Original und Text und Vollbild lassen
// ihn stehen. Gearbeitet wird an einer Kopie; das Buch bleibt, wie es ist. Jede Kopie ist bei jeder Änderung sofort im
// Browser gemerkt (wie die Schnellnotiz) und wird nie von selbst aufgeräumt. Editor und Debugger kommen erst mit dem
// Fenster (lib/schale/Ausfuehrfenster.svelte); hier steht nichts davon.
import type { Codesprache } from "../api/ausfuehren";
import { navigate } from "../router.svelte";
import { liesJson, merkeJson } from "../speicher";

/** Eine erkannte Codestelle, wie der Leser sie zum Ausführen übergibt (Wahrheit: der Begleiter codestellen.json) */
export interface Listing {
  buch: number;
  /** Kurzer Titel des Buchs für den Kopf des Fensters */
  buchtitel: string;
  kennung: string;
  /** Kastentitel oder Beschriftung, etwa "Ausprobieren"; leer ohne */
  titel: string;
  /** Datei aus Titel oder Dateizeile, etwa "kap01/schaetzer.py"; leer ohne */
  datei: string;
  sprache: Codesprache;
  /** Code aus dem Buch, über alle Teile der Stelle am Stück */
  code: string;
  pruefsumme: string;
  /** Gedruckte Seiten der Teile, etwa "8-9" */
  seiten: string;
  /** Weg zur Stelle im Leser, etwa "/book/4784/read?page=20" */
  adresse: string;
}

/** Die Kopie einer Stelle und was dazu gemerkt ist */
export interface Kopie {
  /** Das Original, wie es zuletzt aus dem Buch kam */
  listing: Listing;
  code: string;
  sprache: Codesprache;
  /** Gewählte Fassung der Sprache; leer: die neueste */
  fassung: string;
  haltepunkte: number[];
  /** Zeit der letzten eigenen Änderung; leer: nie geändert */
  geaendert: string;
}

interface Fensterstand {
  offen: boolean;
  tabs: string[];
  aktiv: string;
  abgelegt: boolean;
}

const KOPIE = "bf-ausfuehren:";
const FENSTER = "bf-ausfuehren-fenster";
const OHNE: Fensterstand = { offen: false, tabs: [], aktiv: "", abgelegt: false };

export const schluessel = (buch: number, kennung: string): string => `${buch}:${kennung}`;

const liesKopie = (k: string): Kopie | null => liesJson<Kopie | null>(KOPIE + k, null);

class Ausfuehren {
  offen = $state(false);
  /** Als Leiste abgelegt: alles bleibt, nur zusammengelegt */
  abgelegt = $state(false);
  tabs = $state<string[]>([]);
  aktiv = $state("");
  #kopien = $state<Record<string, Kopie>>({});

  constructor() {
    const f = { ...OHNE, ...liesJson<Partial<Fensterstand>>(FENSTER, {}) };
    const kopien: Record<string, Kopie> = {};
    for (const k of f.tabs) {
      const kopie = liesKopie(k);
      if (kopie) kopien[k] = kopie;
    }
    this.#kopien = kopien;
    this.tabs = f.tabs.filter((k) => kopien[k]);
    this.aktiv = this.tabs.includes(f.aktiv) ? f.aktiv : (this.tabs[0] ?? "");
    this.offen = f.offen && this.tabs.length > 0;
    this.abgelegt = f.abgelegt;
  }

  /** Kopie eines offenen Tabs */
  kopie(k: string): Kopie | null {
    return this.#kopien[k] ?? null;
  }

  /** Steht diese Stelle gerade im Fenster? (LED in der Taste, Streifen an allen Teilen) */
  istOffen(buch: number, kennung: string): boolean {
    return this.offen && this.tabs.includes(schluessel(buch, kennung));
  }

  /** Öffnet ein Listing als Tab, die übrigen bleiben. Eine unveränderte Kopie folgt dem Buch, eine eigene bleibt. */
  oeffne(listing: Listing): void {
    const k = schluessel(listing.buch, listing.kennung);
    const alt = this.#kopien[k] ?? liesKopie(k);
    this.#setze(k, alt
      ? { ...alt, listing, code: alt.geaendert ? alt.code : listing.code }
      : { listing, code: listing.code, sprache: listing.sprache, fassung: "", haltepunkte: [], geaendert: "" });
    if (!this.tabs.includes(k)) this.tabs = [...this.tabs, k];
    this.aktiv = k;
    this.offen = true;
    this.abgelegt = false;
    this.#merkeFenster();
  }

  /** Ändert die Kopie; geändert heißt: der Code weicht vom Buch ab */
  aendere(k: string, teil: Partial<Pick<Kopie, "code" | "sprache" | "fassung" | "haltepunkte">>): void {
    const alt = this.#kopien[k];
    if (!alt) return;
    const neu = { ...alt, ...teil };
    if (teil.code !== undefined && teil.code !== alt.code) neu.geaendert = teil.code === alt.listing.code ? "" : new Date().toISOString();
    this.#setze(k, neu);
  }

  /** Wieder das Listing aus dem Buch; fragt vorher, wer es aufruft */
  zuruecksetzen(k: string): void {
    const alt = this.#kopien[k];
    if (alt) this.#setze(k, { ...alt, code: alt.listing.code, geaendert: "" });
  }

  waehle(k: string): void {
    if (!this.tabs.includes(k)) return;
    this.aktiv = k;
    this.#merkeFenster();
  }

  /** Schließt einen Tab; die Kopie bleibt gemerkt und ist beim nächsten Öffnen der Stelle wieder da */
  schliesseTab(k: string): void {
    const n = this.tabs.indexOf(k);
    if (n < 0) return;
    this.tabs = this.tabs.filter((t) => t !== k);
    if (this.aktiv === k) this.aktiv = this.tabs[Math.min(n, this.tabs.length - 1)] ?? "";
    if (!this.tabs.length) this.offen = false;
    this.#merkeFenster();
  }

  ablegen(): void {
    this.abgelegt = true;
    this.#merkeFenster();
  }

  aufnehmen(): void {
    this.abgelegt = false;
    this.#merkeFenster();
  }

  /** Schließt das Fenster; Tabs und Kopien bleiben für das nächste Öffnen */
  schliesse(): void {
    this.offen = false;
    this.#merkeFenster();
  }

  zurStelle(k: string): void {
    const kopie = this.#kopien[k];
    if (kopie) navigate(kopie.listing.adresse);
  }

  #setze(k: string, kopie: Kopie): void {
    this.#kopien[k] = kopie;
    merkeJson(KOPIE + k, kopie);
  }

  #merkeFenster(): void {
    merkeJson(FENSTER, { offen: this.offen, tabs: this.tabs, aktiv: this.aktiv, abgelegt: this.abgelegt } satisfies Fensterstand);
  }
}

export const ausfuehren = new Ausfuehren();
