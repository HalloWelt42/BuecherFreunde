// Codestellen des offenen Buchs für die Tasten im Leser (BF-29): vom Server erkannt (Begleiter codestellen.json), im PDF in
// Fenstern von Seiten geholt, sonst einmal fürs ganze Buch. Nur mit angeschlossener Sandbox; ohne sie gibt es keine Taste.
// Kommt die Erkennung erst dran oder läuft die Vorprüfung noch, fragt der Leser nach kurzer Zeit wieder.
import { holeCodestellen, istCodesprache, type Codestelle } from "../api/ausfuehren";
import { textSeiten } from "../api/books";
import type { Listing } from "../stand/ausfuehren.svelte";

const FENSTER = 40;
const WIEDER_MS = 4000;
const VERSUCHE = 30;

export class Codestellenstand {
  /** Ausführbare Stellen nach Kennung */
  #stellen = $state.raw<Map<string, Codestelle>>(new Map());
  #geholt = new Set<number>();
  #ganz = false;
  #versuche = 0;
  #uhr: ReturnType<typeof setTimeout> | undefined;
  /** Gedruckte Seitenzahlen, die der Server kennt, wo die Datei keine nennt */
  #gedruckt = $state.raw<Map<number, string>>(new Map());
  #gefragt = new Set<number>();

  /** ausDatei: gedruckte Seite aus der Datei selbst (Seitenbeschriftung des PDF), leer, wenn sie keine nennt */
  constructor(readonly buch: number, readonly pdf: boolean, private ausDatei: (nr: number) => string = () => "") {}

  /** Wie die Seite im Buch heißt ("8"), für "Fortsetzung von S. 8" und den Kopf des Fensters */
  seitenname(nr: number): string {
    const datei = this.ausDatei(nr);
    if (datei || !this.pdf) return datei || String(nr);
    const bekannt = this.#gedruckt.get(nr);
    // Beim Zeichnen gefragt: erst die Antwort ändert den Zustand
    if (bekannt === undefined && !this.#gefragt.has(nr)) {
      this.#gefragt.add(nr);
      void textSeiten(this.buch, nr, 1).then((a) => {
        const wert = a?.seiten?.[0]?.gedruckt ?? "";
        if (wert) this.#gedruckt = new Map(this.#gedruckt).set(nr, wert);
      }).catch(() => {});
    }
    return bekannt || String(nr);
  }

  /** Wie seitenname, wartet aber auf den Server, wo die Datei keine Zahl nennt */
  async seitennameGewiss(nr: number): Promise<string> {
    const datei = this.ausDatei(nr);
    if (datei || !this.pdf) return datei || String(nr);
    if (this.#gedruckt.get(nr)) return this.#gedruckt.get(nr)!;
    const a = await textSeiten(this.buch, nr, 1).catch(() => null);
    const wert = a?.seiten?.[0]?.gedruckt ?? "";
    if (wert) this.#gedruckt = new Map(this.#gedruckt).set(nr, wert);
    return wert || String(nr);
  }

  get alle(): Codestelle[] {
    return [...this.#stellen.values()];
  }

  /** Stellen mit einem Teil auf dieser Dateiseite (nur PDF) */
  aufSeite(nr: number): Codestelle[] {
    return this.alle.filter((s) => s.teile.some((t) => t.seite === nr));
  }

  stelle(kennung: string): Codestelle | null {
    return this.#stellen.get(kennung) ?? null;
  }

  /** Holt, was um diese Seite liegt (PDF), sonst das ganze Buch */
  lade(nr = 1): void {
    if (!this.pdf) {
      if (!this.#ganz) void this.#hole();
      return;
    }
    const fenster = Math.floor((nr - 1) / FENSTER);
    if (this.#geholt.has(fenster)) return;
    this.#geholt.add(fenster);
    void this.#hole(fenster * FENSTER + 1, (fenster + 1) * FENSTER, fenster);
  }

  async #hole(von?: number, bis?: number, fenster?: number): Promise<void> {
    if (fenster === undefined) this.#ganz = true;
    try {
      const a = await holeCodestellen(this.buch, von, bis);
      if (a.stand === "ausstehend") return this.#spaeter(von, fenster);
      const neu = new Map(this.#stellen);
      for (const s of a.stellen) if (s.ausfuehrbar && istCodesprache(s.sprache)) neu.set(s.kennung, s);
      this.#stellen = neu;
      // Die Vorprüfung läuft noch: ihr Punkt kommt mit einem späteren Blick
      if (a.stellen.some((s) => s.ausfuehrbar && s.vorpruefung?.stand === "offen")) this.#spaeter(von, fenster);
    } catch {
      this.#spaeter(von, fenster);
    }
  }

  // Die Erkennung läuft noch oder der Server schwieg: dasselbe Stück später noch einmal
  #spaeter(von: number | undefined, fenster: number | undefined): void {
    if (fenster !== undefined) this.#geholt.delete(fenster);
    else this.#ganz = false;
    if (++this.#versuche > VERSUCHE) return;
    clearTimeout(this.#uhr);
    this.#uhr = setTimeout(() => this.lade(von ?? 1), WIEDER_MS);
  }

  beende(): void {
    clearTimeout(this.#uhr);
  }
}

/** Was das Fenster Ausführen von einer Stelle braucht; seitenname: gedruckte Seite zu einer Dateiseite */
export function listingAus(s: Codestelle, buch: { id: number; title: string }, adresse: string, seiten = ""): Listing {
  return {
    buch: buch.id, buchtitel: buch.title.split(" - ")[0].trim(), kennung: s.kennung, titel: s.titel.split(" - ")[0].trim(), datei: s.datei || dateiAusTitel(s.titel),
    sprache: istCodesprache(s.sprache) ? s.sprache : "python", code: s.code, pruefsumme: s.pruefsumme, seiten, adresse,
  };
}

/** "Ausprobieren - kap01/schaetzer.py" nennt die Datei im Titel */
function dateiAusTitel(titel: string): string {
  return titel.match(/[\w./-]+\.(?:py|js|mjs|php)\b/)?.[0] ?? "";
}
