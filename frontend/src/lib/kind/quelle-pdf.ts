// Ein PDF im Kinderleser: Einheit ist die Seite, ihr Inhalt der Textauszug des Servers (wie in der Textansicht des normalen
// Lesers, lib/leser/pdf/textseiten.svelte.ts) mit Überschriften, Absätzen und den Bildern der Seite. Der Text einer Seite ist
// derselbe wie beim Vorlesen im normalen Leser (lib/leser/pdf/lesequelle.ts).
import { textBildUrl, textSeiten } from "../api/books";
import type { Lesewerte } from "../lesestand";
import type { Baustein, Textantwort } from "../leser/pdf/textseiten.svelte";
import { einheitAus, type Kinderquelle, type Stueck } from "./inhalt";
import type { Einheit, Kinderstelle } from "./typen";

/** So viele Seiten holt eine Anfrage */
const VORAUS = 4;

function stueckeAus(buch: number, seite: number, bausteine: Baustein[]): Stueck[] {
  const aus: Stueck[] = [];
  const nimm = (b: Baustein) => {
    if (b.art === "bild") {
      if (b.bild !== null) aus.push({ art: "bild", bild: { adresse: textBildUrl(buch, seite, b.bild), verhaeltnis: b.verhaeltnis, text: b.text } });
    } else if (b.art === "kasten") {
      aus.push({ art: "titel", text: b.titel });
      b.inhalt.forEach(nimm);
    } else if (b.art !== "code" && b.art !== "tabelle") {
      aus.push({ art: b.art === "ueberschrift" ? "titel" : "absatz", text: b.text });
    }
  };
  bausteine.forEach(nimm);
  return aus;
}

export class Pdfkinderquelle implements Kinderquelle {
  readonly art = "pdf";
  #seiten = new Map<number, Promise<Einheit>>();

  private constructor(private buch: number, readonly anzahl: number, erste: Textantwort) {
    this.#lege(erste);
  }

  static async oeffne(buch: number, ab = 1): Promise<Pdfkinderquelle> {
    const erste = (await textSeiten(buch, Math.max(1, ab), VORAUS)) as Textantwort;
    return new Pdfkinderquelle(buch, Math.max(1, erste.gesamt), erste);
  }

  #lege(antwort: Textantwort): Map<number, Einheit> {
    const neu = new Map<number, Einheit>();
    for (const s of antwort.seiten ?? []) neu.set(s.nr - 1, einheitAus(s.nr - 1, stueckeAus(this.buch, s.nr, s.bausteine)));
    for (const [nr, e] of neu) this.#seiten.set(nr, Promise.resolve(e));
    return neu;
  }

  name(einheit: number): string {
    return `Seite ${einheit + 1}`;
  }

  /** Eine Seite; fehlt sie, kommt sie mit den nächsten in einer Anfrage */
  einheit(nr: number): Promise<Einheit> {
    const da = this.#seiten.get(nr);
    if (da) return da;
    const geholt = textSeiten(this.buch, nr + 1, VORAUS).then((a: Textantwort) => this.#lege(a));
    for (let n = nr; n < Math.min(this.anzahl, nr + VORAUS); n++) {
      if (this.#seiten.has(n)) continue;
      const seite = n;
      const kommt = geholt.then((neu) => neu.get(seite) ?? einheitAus(seite, []));
      // Scheitert die Anfrage, fragt der nächste Versuch neu
      kommt.catch(() => this.#seiten.get(seite) === kommt && this.#seiten.delete(seite));
      this.#seiten.set(seite, kommt);
    }
    return this.#seiten.get(nr) ?? Promise.resolve(einheitAus(nr, []));
  }

  async lesewerte(stelle: Kinderstelle): Promise<Lesewerte> {
    return { page: stelle.einheit + 1 };
  }

  async stelleAus(werte: Lesewerte): Promise<Kinderstelle | null> {
    return werte.page ? { einheit: Math.min(this.anzahl - 1, Math.max(0, werte.page - 1)), zeichen: 0 } : null;
  }

  async markierungsort(einheit: number): Promise<string> {
    return `page:${einheit + 1}`;
  }

  async einheitDer(ort: string): Promise<number | null> {
    const nr = Number(/^page:(\d+)/.exec(ort)?.[1]);
    return nr >= 1 && nr <= this.anzahl ? nr - 1 : null;
  }

  ort(stelle: Kinderstelle): string {
    return `S.${stelle.einheit + 1}`;
  }

  schliesse(): void {
    this.#seiten.clear();
  }
}

