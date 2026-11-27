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

/** Woher der Text einer Seite kommt (BF-109): Textschicht des PDF, Texterkennung, noch in der Erkennung, ohne lesbaren Text */
export type Schicht = "pdf" | "erkannt" | "wartet" | "ohne";

export interface Textseite {
  nr: number;
  gedruckt: string | null;
  bausteine: Baustein[];
  /** fehlt: aus der Textschicht des PDF */
  schicht?: Schicht;
}

export interface Textantwort {
  gesamt: number;
  seiten: Textseite[];
}

/** Trägt ein Baustein lesbaren Text, auch in einem Kasten? */
const mitText = (b: Baustein): boolean => (b.art !== "bild" && !!(b.text.trim() || b.titel.trim() || b.zeilen?.length)) || b.inhalt.some(mitText);

type Hole = (buch: number, ab: number, anzahl: number) => Promise<Textantwort>;

export const AUSSCHNITT = 6;
/** So viele Seiten gibt der Server je Anfrage höchstens (GET /api/books/{id}/textseiten, anzahl) */
export const AUSSCHNITT_HOECHSTENS = 30;

export class Textseiten {
  seiten = $state.raw<Textseite[]>([]);
  gesamt = $state(0);
  laedt = $state(false);
  fehler = $state("");

  erste = $derived(this.seiten[0]?.nr ?? 1);
  letzte = $derived(this.seiten.at(-1)?.nr ?? 0);
  /** Seiten, deren Text die Texterkennung noch liest */
  wartend = $derived(this.seiten.filter((s) => s.schicht === "wartet").map((s) => s.nr));
  /** Nur Bilder, kein lesbarer Text (eingescannt) und keiner unterwegs: die Seitenbilder zählen nicht als Text */
  ohneText = $derived(this.seiten.length > 0 && !this.seiten.some((s) => s.bausteine.some(mitText)) && !this.wartend.length);
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

  /** Diese Seiten sind erkannt: neu holen und an ihrer Stelle einsetzen, mit je einer Nachbarseite (ein Absatz über den
   *  Seitenwechsel steht ganz auf der nächsten) */
  async erneuere(nrn: number[]): Promise<boolean> {
    const geladen = new Set(this.seiten.map((s) => s.nr));
    const da = nrn.filter((n) => geladen.has(n));
    if (!da.length) return false;
    const ab = Math.max(this.erste, Math.min(...da) - 1);
    const bis = Math.min(this.letzte, Math.max(...da) + 1, ab + AUSSCHNITT_HOECHSTENS - 1);
    return this.#lade(ab, (neue) => {
      const neu = new Map(neue.filter((s) => s.nr <= bis).map((s) => [s.nr, s]));
      this.seiten = this.seiten.map((s) => neu.get(s.nr) ?? s);
    }, bis - ab + 1);
  }

  async #lade(ab: number, setze: (neue: Textseite[]) => void, anzahl = AUSSCHNITT): Promise<boolean> {
    if (this.laedt) return false;
    this.laedt = true;
    this.fehler = "";
    try {
      const antwort = await this.hole(this.buch, ab, anzahl);
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
