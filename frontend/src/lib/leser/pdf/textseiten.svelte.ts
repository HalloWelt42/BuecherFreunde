// Die Textseiten eines PDF in Ausschnitten: ab der gelesenen Seite, unten und oben nachgeladen
import { textSeiten } from "../../api/books";

export interface Baustein {
  art: "ueberschrift" | "absatz" | "unterschrift" | "bild" | "kasten" | "code";
  text: string;
  titel: string;
  inhalt: Baustein[];
  bild: number | null;
  verhaeltnis: number | null;
  breite_em: number | null;
  /** Codestelle (BF-29): Zeilen dieses Teils, Sprache, Kennung der Stelle, der wievielte Teil von wie vielen */
  zeilen?: string[];
  sprache?: string | null;
  kennung?: string;
  teil?: number | null;
  teile?: number | null;
}

export interface Textseite {
  nr: number;
  gedruckt: string | null;
  bausteine: Baustein[];
}

export interface Textantwort {
  gesamt: number;
  seiten: Textseite[];
}

type Hole = (buch: number, ab: number, anzahl: number) => Promise<Textantwort>;

export const AUSSCHNITT = 6;

export class Textseiten {
  seiten = $state.raw<Textseite[]>([]);
  gesamt = $state(0);
  laedt = $state(false);
  fehler = $state("");

  erste = $derived(this.seiten[0]?.nr ?? 1);
  letzte = $derived(this.seiten.at(-1)?.nr ?? 0);
  ohneText = $derived(this.seiten.length > 0 && this.seiten.every((s) => s.bausteine.length === 0));
  mitVorn = $derived(this.seiten.length > 0 && this.erste > 1);
  mitHinten = $derived(this.letzte > 0 && this.letzte < this.gesamt);

  /** einbauen: so wird der Text ergänzt, ohne dass die gelesene Stelle springt */
  constructor(private buch: number, private einbauen: (tun: () => unknown) => Promise<void>, private hole: Hole = textSeiten) {}

  async neu(ab: number): Promise<boolean> {
    return this.#lade(ab, (neue) => (this.seiten = neue));
  }

  async unten(): Promise<boolean> {
    if (!this.mitHinten) return false;
    return this.#lade(this.letzte + 1, (neue) => (this.seiten = [...this.seiten, ...neue.filter((s) => s.nr > this.letzte)]));
  }

  async oben(): Promise<boolean> {
    if (!this.mitVorn) return false;
    const ab = Math.max(1, this.erste - AUSSCHNITT);
    return this.#lade(ab, (neue) => (this.seiten = [...neue.filter((s) => s.nr < this.erste), ...this.seiten]));
  }

  async #lade(ab: number, setze: (neue: Textseite[]) => void): Promise<boolean> {
    if (this.laedt) return false;
    this.laedt = true;
    this.fehler = "";
    try {
      const antwort = await this.hole(this.buch, ab, AUSSCHNITT);
      this.gesamt = antwort.gesamt;
      await this.einbauen(() => setze(antwort.seiten));
      return true;
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
      return false;
    } finally {
      this.laedt = false;
    }
  }
}
