// Die Liste der Bibliothek: Filter aus der Adresse, Sortierung gemerkt, Nachladen seitenweise
import { listeBooks } from "../api/books";
import { liesJson, merkeJson } from "../speicher";
import type { Buch, BuchListe } from "../typen";
import { filter } from "./filter.svelte";

const JE_SEITE = 48;
const SORT_SCHLUESSEL = "lib_sort";

export type Sortierung = "titel" | "autor" | "datum" | "groesse" | "jahr" | "bewertung" | "verlag";
export type Richtung = "asc" | "desc";

export const sortierungen: [Sortierung, string, Richtung][] = [
  ["datum", "Zuletzt hinzugefügt", "desc"], ["titel", "Titel", "asc"], ["autor", "Autor", "asc"], ["jahr", "Jahr", "desc"], ["bewertung", "Bewertung", "desc"], ["groesse", "Dateigröße", "desc"], ["verlag", "Verlag", "asc"],
];

const gemerkt = liesJson<{ by?: Sortierung; dir?: Richtung }>(SORT_SCHLUESSEL, {});

class Buecher {
  liste = $state<Buch[]>([]);
  gesamt = $state(0);
  laedt = $state(false);
  fehler = $state("");
  geladen = $state(false);
  sortierung = $state<Sortierung>(gemerkt.by ?? "datum");
  richtung = $state<Richtung>(gemerkt.dir ?? "desc");
  /** Filter, zu denen die Liste gehört */
  kennung = "";
  #seite = 0;
  #lauf = 0;

  #parameter(seite: number, jeSeite = JE_SEITE): Record<string, string | number | boolean> {
    const p: Record<string, string | number | boolean> = { seite, pro_seite: jeSeite, sortierung: this.sortierung, richtung: this.richtung };
    const uebersetzt: [string, string][] = [["category", "kategorie"], ["sammlung", "sammlung"], ["file_format", "format"], ["min_rating", "bewertung_min"], ["is_favorite", "favorit"], ["is_to_read", "zu_lesen"], ["gelesen", "gelesen"], ["hat_isbn", "hat_isbn"], ["hat_highlights", "hat_highlights"], ["hat_labels", "hat_labels"], ["weiterlesen", "weiterlesen"]];
    for (const [von, zu] of uebersetzt) {
      // Alte Adressen können bei Sammlung und Bewertung mehrere Werte tragen; der Server kennt dort nur einen
      const w = ["sammlung", "min_rating"].includes(von) ? filter.werte(von)[0] : filter.wert(von);
      if (w) p[zu] = w;
    }
    return p;
  }

  /** Von vorn: neue Filter, neue Sortierung */
  async laden(): Promise<void> {
    this.kennung = filter.kennung;
    await this.#hole(1, () => listeBooks(this.#parameter(1)), false);
  }

  async mehr(): Promise<void> {
    if (this.laedt || this.liste.length >= this.gesamt) return;
    const seite = this.#seite + 1;
    await this.#hole(seite, () => listeBooks(this.#parameter(seite)), true);
  }

  /** Denselben Ausschnitt neu holen (nach Änderungen), ohne zum Anfang zu springen und ohne Doppel */
  async auffrischen(): Promise<void> {
    const seiten = Math.max(1, this.#seite);
    await this.#hole(seiten, async () => {
      const teile = await Promise.all(Array.from({ length: seiten }, (_, n) => listeBooks(this.#parameter(n + 1))));
      return { ...teile[0], buecher: teile.flatMap((t) => t.buecher) };
    }, false);
  }

  async #hole(seite: number, hole: () => Promise<BuchListe>, anhaengen: boolean): Promise<void> {
    const lauf = ++this.#lauf;
    this.laedt = true;
    this.fehler = "";
    try {
      const antwort = await hole();
      if (lauf !== this.#lauf) return;
      const bekannt = new Set(anhaengen ? this.liste.map((b) => b.id) : []);
      this.liste = anhaengen ? [...this.liste, ...antwort.buecher.filter((b) => !bekannt.has(b.id))] : antwort.buecher;
      this.gesamt = antwort.gesamt;
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

  /** Dieselbe Spalte noch einmal dreht die Richtung */
  sortiere(nach: Sortierung): void {
    if (nach === this.sortierung) this.richtung = this.richtung === "asc" ? "desc" : "asc";
    else {
      this.sortierung = nach;
      this.richtung = sortierungen.find(([s]) => s === nach)?.[2] ?? "asc";
    }
    this.#merke();
  }

  dreheRichtung(): void {
    this.richtung = this.richtung === "asc" ? "desc" : "asc";
    this.#merke();
  }

  #merke(): void {
    merkeJson(SORT_SCHLUESSEL, { by: this.sortierung, dir: this.richtung });
    void this.laden();
  }

  /** Ein einzelnes Buch in der Liste ändern (Favorit, Sterne, Lesesofa) */
  aktualisiere(id: number, neu: Partial<Buch>): void {
    this.liste = this.liste.map((b) => (b.id === id ? { ...b, ...neu } : b));
  }
}

export const buecher = new Buecher();
