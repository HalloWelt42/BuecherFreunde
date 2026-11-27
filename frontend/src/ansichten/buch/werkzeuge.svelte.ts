// Die Werkzeuge für die Angaben eines Buchs (BF-111, BF-112): welches Fenster offen ist, die ISBN-Suche mit ihren Kandidaten und
// was davon geprüft ist. Ein Stand für Werkzeugreihe, Feld ISBN und Fenster; beim Bearbeiten geht Übernommenes ins Formular,
// sonst ins Buch (ziel.ts). Wechselt man vom Vergleich zurück zu den Kandidaten, bleibt alles, wie es war.
import { isbnPruefen, isbnScan, isbnZurWahl, type Isbnkandidat, type Isbnsuche } from "../../lib/api/books";
import { melde } from "../../lib/stand/meldungen.svelte";
import { quellen } from "../../lib/stand/quellen.svelte";
import { ALLE } from "./angaben";
import { ruhemeldung, vorwahl, type Isbnzeile } from "./isbn";
import type { Angabenziel } from "./ziel";

/** isbn im Vergleich: null die gespeicherte, leer ohne ISBN (über Titel und Autor), sonst nur diese */
export type Angabenfenster =
  | { art: "vergleich"; quelle: string; isbn: string | null; kandidat: Isbnkandidat | null }
  | { art: "isbn" }
  | { art: "buchtext" }
  | { art: "ki" };

/** Was die Werkzeuge vom Buch brauchen */
export interface Werkzeugbuch {
  id: number;
  title: string;
  file_format: string;
}

export class Angabenwerkzeuge {
  fenster = $state<Angabenfenster | null>(null);
  suche = $state<Isbnsuche | null>(null);
  zeilen = $state<Isbnzeile[]>([]);
  /** ISBN der gewählten Zeile */
  gewaehlt = $state("");
  sucht = $state(false);
  /** Im Buch steht keine ISBN (oder es hat keinen Text) */
  nichts = $state(false);
  holtUmschlag = $state(false);
  /** ISBN zur Wahl aus dem Lauf "ISBN" (BF-111, Abnahme 5) */
  zurWahl = $state<Isbnkandidat[]>([]);
  readonly buch: Werkzeugbuch;
  readonly ziel: Angabenziel;

  constructor(buch: Werkzeugbuch, ziel: Angabenziel) {
    this.buch = buch;
    this.ziel = ziel;
  }

  /** Alle, wenn es mehrere Quellen gibt, sonst die eine */
  get standardquelle(): string {
    return quellen.buecher.length > 1 ? ALLE : (quellen.buecher[0]?.kennung ?? ALLE);
  }

  oeffne(art: "buchtext" | "ki"): void {
    this.fenster = { art };
  }

  vergleiche(quelle: string, isbn: string | null = null, kandidat: Isbnkandidat | null = null): void {
    this.fenster = { art: "vergleich", quelle, isbn, kandidat };
  }

  /** Vom Vergleich zurück zu den Kandidaten */
  zurueck(): void {
    this.fenster = this.suche ? { art: "isbn" } : null;
  }

  schliesse(): void {
    this.fenster = null;
  }

  #zeige(s: Isbnsuche): void {
    this.suche = s;
    this.zeilen = s.kandidaten.map((kandidat) => ({ kandidat, pruefung: null, prueft: false }));
    this.gewaehlt = vorwahl(s.kandidaten);
    this.fenster = { art: "isbn" };
  }

  /** Im ganzen Buch suchen; ohne Fund öffnet sich kein Fenster, das Feld sagt es in einem Satz */
  async sucheIsbn(): Promise<void> {
    this.sucht = true;
    this.nichts = false;
    try {
      const s = await isbnScan(this.buch.id);
      if (s.kandidaten.length) this.#zeige(s);
      else this.nichts = true;
    } catch (e) {
      melde.schlecht(e, "ISBN nicht gesucht");
    } finally {
      this.sucht = false;
    }
  }

  /** Die ISBN zur Wahl dieses Buchs laden (nur am Feld ISBN, solange das Buch keine hat) */
  async ladeZurWahl(): Promise<void> {
    try {
      this.zurWahl = await isbnZurWahl(this.buch.id);
    } catch {
      this.zurWahl = [];                 // ohne Liste bleibt das Feld, wie es ist; suchen geht weiter
    }
  }

  /** Nur auf Tippen, je ISBN einzeln (BF-111): die Quellen der Reihe nach bis zum ersten Fund */
  async pruefe(isbn: string): Promise<void> {
    const zeile = this.zeilen.find((z) => z.kandidat.isbn === isbn);
    if (!zeile || zeile.prueft) return;
    zeile.prueft = true;
    try {
      const p = await isbnPruefen(this.buch.id, isbn);
      zeile.pruefung = p;
      if (p.hinweise.length) melde.warn(ruhemeldung(p));
    } catch (e) {
      melde.schlecht(e, "Nicht geprüft");
    } finally {
      zeile.prueft = false;
    }
  }

  get kandidat(): Isbnkandidat | null {
    return this.zeilen.find((z) => z.kandidat.isbn === this.gewaehlt)?.kandidat ?? null;
  }

  async isbnUebernehmen(): Promise<void> {
    if (!this.gewaehlt) return;
    try {
      await this.ziel.isbn(this.gewaehlt);
      this.zurWahl = [];
      this.schliesse();
    } catch (e) {
      melde.schlecht(e, "ISBN nicht übernommen");
    }
  }

  async umschlag(): Promise<void> {
    this.holtUmschlag = true;
    try {
      await this.ziel.umschlagAusDatei();
    } catch (e) {
      melde.schlecht(e, "Umschlag nicht geholt, der bisherige bleibt");
    } finally {
      this.holtUmschlag = false;
    }
  }
}
