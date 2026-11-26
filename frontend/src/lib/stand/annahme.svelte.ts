// Die Annahme in der Oberfläche: Einträge des Servers (Ereignisstrom) zusammen mit dem, was dieser Browser hochlädt. Eine
// Liste für alle Quellen; einzeln gezeigt wird, was jemand hochlädt oder ablegt, Ordner und gemeinfreie Bücher als ein Auftrag.
// Was vor dem Regal auf die Bestätigung wartet, steht je Vorschau als eine Zeile (BF-80).
import { annahmeDienst, annahmeEreignisse, annahmeErneut, blendeAnnahmenAus, entferneAnnahme, ladeAnnahmen, legeVorschauAn, raeumeAnnahmeAuf } from "../api/annahme";
import { hochladenZaehlen } from "../api/client";
import { Hochlader } from "../annahme/hochlader";
import { pruefsumme } from "../annahme/pruefsumme";
import type { AnnahmeEintrag, AnnahmeListe, Annahmequelle, AnnahmeZaehler, Hochladung, Quellenzahlen, Vorschaukurz } from "../annahme/typen";
import { anzahl } from "../format";
import { EINLESEN, EINZELN, GEMEINFREI, gehoertZu, sammle } from "../annahme/sammlung";
import { fuegeZusammen, laeuftVonSelbst, type Annahmezeile } from "../annahme/zeilen";
import { darfAbrufen } from "./abrufe";
import { bestand } from "./bestand.svelte";

const IM_REGAL = ["wissen", "fertig", "ohne_text"];
const LEER: AnnahmeZaehler = { alle: 0, laeuft: 0, klaeren: 0, da: 0, fertig: 0 };
const AUFFRISCHEN_MS = 800;

class Annahme {
  eintraege = $state<AnnahmeEintrag[]>([]);
  zaehler = $state<AnnahmeZaehler>(LEER);
  /** Zahlen je Quelle über alle Einträge, vom Server */
  quellen = $state<Partial<Record<Annahmequelle, Quellenzahlen>>>({});
  /** Offene Vorschauen, die neueste zuerst ("Zum Bestätigen") */
  vorschauen = $state<Vorschaukurz[]>([]);
  hochladungen = $state<Hochladung[]>([]);
  /** Antwortet der Server auf die Annahme? Vor der ersten Antwort unbekannt */
  grund = $state("");
  geladen = $state(false);

  zeilen = $derived<Annahmezeile[]>(fuegeZusammen(this.eintraege.filter((e) => gehoertZu(e, EINZELN)), this.hochladungen, this.vorschauen));
  /** Einlesen aus dem Einlese-Ordner und der externen Sammlung */
  einlesen = $derived(sammle(this.eintraege, EINLESEN, this.quellen));
  /** Gemeinfreie Bücher holen */
  gemeinfrei = $derived(sammle(this.eintraege, GEMEINFREI, this.quellen));
  laufend = $derived(this.zeilen.filter((z) => z.gruppe === "laeuft"));
  vonSelbst = $derived(this.laufend.filter(laeuftVonSelbst).length);
  angehalten = $derived(this.laufend.length - this.vonSelbst);

  #hochlader = new Hochlader(annahmeDienst, pruefsumme);
  #stromAus: (() => void) | null = null;
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #zaehlt = false;

  constructor() {
    this.#hochlader.beiAenderung((liste) => {
      this.hochladungen = liste;
      if (this.#hochlader.laeuft !== this.#zaehlt) {
        this.#zaehlt = this.#hochlader.laeuft;
        hochladenZaehlen(this.#zaehlt ? 1 : -1);
      }
    });
    if (typeof window !== "undefined") addEventListener("online", () => this.#hochlader.verbindungDa());
  }

  async starte(): Promise<void> {
    if (this.#stromAus || !darfAbrufen("annahme")) return;
    await this.auffrischen();
    if (!this.grund) this.#stromAus = annahmeEreignisse((liste) => this.#uebernimm(liste));
  }

  halte(): void {
    this.#stromAus?.();
    this.#stromAus = null;
  }

  async auffrischen(): Promise<void> {
    if (!darfAbrufen("annahme")) return;
    try {
      this.#uebernimm(await ladeAnnahmen());
      this.grund = "";
    } catch (e) {
      this.grund = e instanceof Error ? e.message : String(e);
    }
    this.geladen = true;
  }

  #uebernimm(liste: AnnahmeListe): void {
    const vorher = new Map(this.eintraege.map((e) => [e.id, e.stand]));
    const neuImRegal = liste.eintraege.some((e) => IM_REGAL.includes(e.stand) && vorher.has(e.id) && !IM_REGAL.includes(vorher.get(e.id)!));
    this.eintraege = liste.eintraege;
    this.zaehler = liste.zaehler ?? LEER;
    if (liste.quellen) this.quellen = liste.quellen;
    if (liste.vorschauen) this.vorschauen = liste.vorschauen;
    if (!neuImRegal) return;
    clearTimeout(this.#uhr);
    this.#uhr = setTimeout(() => bestand.geaendert(), AUFFRISCHEN_MS);
  }

  /**
   * Hochladen im Browser läuft immer über eine Vorschau (BF-80): erst die leere Vorschau, dann die Dateien in sie. Liefert
   * ihre Kennung, damit die Ansicht gleich dorthin geht, während Prüfsummen und Teile noch laufen.
   */
  async nimmAn(dateien: readonly File[], anreichern: boolean): Promise<string> {
    void this.starte();
    const v = await legeVorschauAn(dateien.length === 1 ? dateien[0].name : anzahl(dateien.length, "Datei", "Dateien"));
    this.vorschauen = [v, ...this.vorschauen.filter((x) => x.id !== v.id)];
    this.#hochlader.fuegeHinzu(dateien, { art: "vorschau", vorschau: v.id, anreichern });
    return v.id;
  }

  /** Begleitmaterial zu einem Buch (BF-81): jede Datei für sich, der Fortschritt steht bei den Aufträgen */
  materialHinzu(buch: number, dateien: readonly File[], entpacken: boolean): void {
    void this.starte();
    this.#hochlader.fuegeHinzu(dateien, { art: "material", buch, entpacken });
  }

  anhalten(schluessel: string): void {
    this.#hochlader.anhalten(schluessel);
  }

  weiter(schluessel: string): void {
    this.#hochlader.weiter(schluessel);
  }

  async erneut(id: number): Promise<void> {
    await annahmeErneut(id);
    await this.auffrischen();
  }

  async entferne(zeile: Annahmezeile): Promise<void> {
    if (zeile.hochladung) this.#hochlader.entferne(zeile.hochladung);
    if (zeile.id !== null) await entferneAnnahme(zeile.id);
    await this.auffrischen();
  }

  async blendeAus(): Promise<void> {
    await blendeAnnahmenAus();
    await this.auffrischen();
  }

  /** Einen Auftrag aufräumen: alle Einträge der Quellen in diesen Ständen, am Server in einem Schritt; Bücher bleiben */
  async raeumeAuf(quellen: readonly Annahmequelle[], staende: readonly string[]): Promise<void> {
    for (const quelle of quellen) this.#uebernimm(await raeumeAnnahmeAuf(quelle, staende));
  }
}

export const annahme = new Annahme();
