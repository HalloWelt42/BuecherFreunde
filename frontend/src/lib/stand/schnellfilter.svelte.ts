// Schnellfilter: auf Wunsch grenzt das Suchfeld die offene Liste ein, statt in allen Büchern zu suchen. Jede Ansicht mit
// Liste bietet dafür ein Ziel an, solange sie offen ist; wo keines ist (Buch, Leser, Suche, Einstellungen), sucht das Feld.
import { untrack } from "svelte";
import { lies, merke } from "../speicher";

/** Was eine Ansicht dem Suchfeld zum Filtern anbietet; wo sie das Wort hält (Adresse, eigener Stand), ist ihre Sache */
export interface Filterziel {
  /** Das Wort, nach dem die Ansicht gerade filtert */
  readonly wort: string;
  /** Platzhalter im Feld: wonach sich filtern lässt */
  readonly hinweis: string;
  /** Wie viele passen, null solange unbekannt */
  readonly treffer: number | null;
  /** Wie viele die Ansicht ohne Schnellfilter zeigt, null solange unbekannt */
  readonly gesamt: number | null;
  /** Neues Wort, schon ohne Leerraum am Rand; leer hebt den Schnellfilter auf */
  filtere(wort: string): void;
}

export type Feldart = "suchen" | "filtern";

const SCHLUESSEL = "suchfeld.art";
/** So lange Ruhe nach der letzten Taste, dann filtert die Ansicht: keine Anfrage je Taste */
export const FILTER_WARTE_MS = 300;

class Schnellfilter {
  #art = $state<Feldart>(lies(SCHLUESSEL) === "filtern" ? "filtern" : "suchen");
  /** Das Ziel der offenen Ansicht; roh, damit seine Getter die Werte der Ansicht lesen */
  ziel = $state.raw<Filterziel | null>(null);
  #uhr: ReturnType<typeof setTimeout> | undefined;

  /** Was das Feld sein soll, je Gerät gemerkt */
  get art(): Feldart {
    return this.#art;
  }

  /** Filtert das Feld gerade? Nur wenn gewünscht und die Ansicht eine Liste hat */
  get filtert(): boolean {
    return this.#art === "filtern" && this.ziel !== null;
  }

  schalte(): void {
    this.#art = this.#art === "filtern" ? "suchen" : "filtern";
    merke(SCHLUESSEL, this.#art);
  }

  /** Eine Ansicht bietet ihre Liste an; liefert das Abmelden für ihr Ende */
  biete(ziel: Filterziel): () => void {
    untrack(() => {
      this.#halte();
      this.ziel = ziel;
    });
    return () =>
      untrack(() => {
        if (this.ziel !== ziel) return;
        this.#halte();
        this.ziel = null;
      });
  }

  /** Beim Tippen: erst nach einer Pause filtern */
  tippe(wort: string): void {
    this.#halte();
    const ziel = this.ziel;
    if (!ziel) return;
    this.#uhr = setTimeout(() => {
      if (this.ziel === ziel) this.#wende(ziel, wort);
    }, FILTER_WARTE_MS);
  }

  /** Gleich filtern (Enter, Leeren, Umschalten) */
  sofort(wort: string): void {
    this.#halte();
    if (this.ziel) this.#wende(this.ziel, wort);
  }

  /** Den Schnellfilter einer Ansicht aufheben (Chip, leerer Zustand) */
  leere(ziel: Filterziel): void {
    if (this.ziel === ziel) this.#halte();
    if (ziel.wort) ziel.filtere("");
  }

  #wende(ziel: Filterziel, wort: string): void {
    const sauber = wort.trim();
    if (sauber !== ziel.wort) ziel.filtere(sauber);
  }

  #halte(): void {
    clearTimeout(this.#uhr);
    this.#uhr = undefined;
  }
}

export const schnellfilter = new Schnellfilter();
