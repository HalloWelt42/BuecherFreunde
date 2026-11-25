// Gemeinfreie Bücher: Suche, Auswahl über alle Seiten und die laufende Übernahme
import { ereignisseGemeinfreie, setzeGemeinfreieZurueck, standGemeinfreie, sucheGemeinfreie, uebernimmGemeinfreie, type Fundbuch, type Uebernahmestand } from "../api/gutenberg";
import { auftraege } from "./auftraege.svelte";
import { bestand } from "./bestand.svelte";

const AUFTRAG = "gutenberg";
const NEU_VERBINDEN_MS = 3000;

class Gutenberg {
  wort = $state("");
  sprache = $state("de");
  treffer = $state<Fundbuch[]>([]);
  gesamt = $state(0);
  seite = $state(1);
  weitere = $state(false);
  laedt = $state(false);
  fehler = $state("");
  gesucht = $state(false);
  stand = $state<Uebernahmestand | null>(null);
  #gewaehlt = $state<ReadonlyMap<number, Fundbuch>>(new Map());

  zahl = $derived(this.#gewaehlt.size);
  alleGewaehlt = $derived(this.treffer.length > 0 && this.treffer.every((b) => this.#gewaehlt.has(b.gutenberg_id)));
  laeuft = $derived(this.stand?.laeuft ?? false);

  #stromAus: (() => void) | null = null;
  #lauf = 0;

  hat(id: number): boolean {
    return this.#gewaehlt.has(id);
  }

  /** Neue Frage, Seite 1; die Auswahl gehört zur alten Frage und fällt weg */
  async suche(): Promise<void> {
    this.#gewaehlt = new Map();
    await this.#hole(1);
  }

  async blaettere(schritt: number): Promise<void> {
    await this.#hole(Math.max(1, this.seite + schritt));
  }

  async #hole(seite: number): Promise<void> {
    const lauf = ++this.#lauf;
    this.laedt = true;
    this.fehler = "";
    try {
      const antwort = await sucheGemeinfreie(this.wort, this.sprache, seite);
      if (lauf !== this.#lauf) return;
      this.treffer = antwort.buecher;
      this.gesamt = antwort.gesamt;
      this.seite = seite;
      this.weitere = !!antwort.naechste;
    } catch (e) {
      if (lauf !== this.#lauf) return;
      this.fehler = e instanceof Error ? e.message : String(e);
      this.treffer = [];
    } finally {
      if (lauf === this.#lauf) {
        this.laedt = false;
        this.gesucht = true;
      }
    }
  }

  schalte(buch: Fundbuch): void {
    const neu = new Map(this.#gewaehlt);
    if (!neu.delete(buch.gutenberg_id)) neu.set(buch.gutenberg_id, buch);
    this.#gewaehlt = neu;
  }

  /** Alle dieser Seite wählen oder abwählen; andere Seiten bleiben, wie sie sind */
  schalteSeite(): void {
    const neu = new Map(this.#gewaehlt);
    const weg = this.alleGewaehlt;
    for (const b of this.treffer) {
      if (weg) neu.delete(b.gutenberg_id);
      else neu.set(b.gutenberg_id, b);
    }
    this.#gewaehlt = neu;
  }

  leere(): void {
    this.#gewaehlt = new Map();
  }

  async uebernimm(): Promise<void> {
    const buecher = [...this.#gewaehlt.values()].map(({ gutenberg_id, titel, autor, download_url, download_format, cover_url }) => ({ gutenberg_id, titel, autor, download_url, download_format, cover_url }));
    await uebernimmGemeinfreie(buecher);
    this.#gewaehlt = new Map();
    this.#setze({ laeuft: true, gesamt: buecher.length, fertig: 0, fehler: 0, duplikate: 0, aktuell: "", ergebnisse: [] });
    this.#verbinde();
  }

  /** Läuft am Server noch eine Übernahme (Seite neu geladen)? Dann dort wieder einsteigen. */
  async pruefe(): Promise<void> {
    if (this.#stromAus) return;
    try {
      const stand = await standGemeinfreie();
      if (stand.gesamt > 0) this.#setze(stand);
      if (stand.laeuft) this.#verbinde();
    } catch {
      // ohne Antwort bleibt der letzte Stand stehen
    }
  }

  #verbinde(): void {
    this.#stromAus?.();
    this.#stromAus = ereignisseGemeinfreie(
      (stand) => {
        this.#setze(stand);
        if (stand.laeuft || stand.gesamt === 0) return;
        this.#trenne();
        bestand.geaendert();
      },
      () => {
        this.#stromAus = null;
        if (this.laeuft) setTimeout(() => void this.pruefe(), NEU_VERBINDEN_MS);
      },
    );
  }

  #trenne(): void {
    this.#stromAus?.();
    this.#stromAus = null;
  }

  async zuruecksetzen(): Promise<void> {
    await setzeGemeinfreieZurueck();
    this.stand = null;
    auftraege.entferne(AUFTRAG);
  }

  #setze(stand: Uebernahmestand): void {
    this.stand = stand;
    const neben = [stand.duplikate ? `${stand.duplikate} gab es schon` : "", stand.fehler ? `${stand.fehler} gescheitert` : ""].filter(Boolean);
    auftraege.setze({
      id: AUFTRAG,
      titel: "Gemeinfreie Bücher holen",
      text: [`${stand.fertig} von ${stand.gesamt}`, stand.laeuft ? stand.aktuell : "fertig", ...neben].filter(Boolean).join(", "),
      anteil: stand.gesamt ? stand.fertig / stand.gesamt : null,
      laeuft: stand.laeuft,
      weg: "/import",
    });
  }
}

export const gutenberg = new Gutenberg();
