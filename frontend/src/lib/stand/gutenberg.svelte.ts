// Gemeinfreie Bücher (BF-98): beim Tippen Vorschläge aus dem eigenen Katalog (kein Dienst im Netz wird gefragt), "Bei Gutendex
// suchen" ausdrücklich, sichtbar wartend und abbrechbar, bei einer Störung die Treffer aus dem Katalog mit einer Meldung in
// Klartext. Der Katalog selbst ist ein Auftrag unter Aufträge: beim ersten Öffnen ohne Katalog von selbst, sonst auf Wunsch.
// Die Auswahl gilt über alle Seiten und Listen, bis geholt oder aufgehoben wird. Geholt wird über die Annahme; ihr Stand steht
// dort (annahme.gemeinfrei), als Auftrag im Kopf zeigt ihn lib/stand/auftraege.svelte.ts.
import { angabenAus, holeKatalog, ladeKatalogstand, schlageGemeinfreieVor, sucheGemeinfreie, uebernimmGemeinfreie, type Fundbuch, type Fundliste, type Katalogstand } from "../api/gutenberg";
import { anzahl, datum, groesse, groesseVon, zahl, zeitspanne } from "../format";
import { annahme } from "./annahme.svelte";
import { auftraege } from "./auftraege.svelte";
import { fehlertext, melde } from "./meldungen.svelte";

/** Woher die gezeigten Treffer kommen; gestoert: aus dem eigenen Katalog, weil Gutendex nicht antwortete */
export type Trefferherkunft = "katalog" | "gutendex" | "gestoert";

export const HERKUNFT: Record<Trefferherkunft, string> = { katalog: "aus dem eigenen Katalog", gutendex: "von Gutendex", gestoert: "aus dem eigenen Katalog, Gutendex gerade gestört" };
/** So lange nach dem letzten Tastendruck kommen die Vorschläge */
export const VERZOEGERUNG_MS = 250;
const UHR_MS = 1000;
const KATALOG_TAKT_MS = 1000;
const AUFTRAG = "gutenberg-katalog";

/** "wöchentlich", "täglich", sonst "alle 10 Tage" */
export function erneuernText(tage: number): string {
  return tage === 7 ? "wöchentlich" : tage === 1 ? "täglich" : `alle ${zahl(tage)} Tage`;
}

/** "Eigener Katalog: 76.012 Bücher, Stand 08.11.2026, wird wöchentlich erneuert" */
export function katalogzeile(k: Katalogstand): string {
  if (!k.da) return k.grund ? `Eigener Katalog fehlt noch: ${k.grund}` : "Eigener Katalog fehlt noch";
  return `Eigener Katalog: ${anzahl(k.anzahl, "Buch", "Bücher")}, Stand ${datum(k.stand)}, wird ${erneuernText(k.erneuern_tage)} erneuert`;
}

/** "Der Suchdienst ist oft langsam. Die App wartet bis zu 2 Minuten; die Vorschläge unten kannst du schon holen." */
export function wartehinweis(geduldS: number | undefined, mitVorschlaegen: boolean): string {
  const teile = [geduldS ? `Die App wartet bis zu ${zeitspanne(geduldS)}` : "", mitVorschlaegen ? "die Vorschläge unten kannst du schon holen" : ""].filter(Boolean).join("; ");
  return `Der Suchdienst ist oft langsam.${teile ? ` ${teile.charAt(0).toUpperCase()}${teile.slice(1)}.` : ""}`;
}

/** Der laufende Katalog in der Karte: was, wie weit, Anteil für den Balken (null: Ende nicht absehbar) */
export function katalogauftrag(k: Katalogstand): { titel: string; text: string; anteil: number | null } {
  const titel = k.da ? "Eigener Katalog wird erneuert" : "Eigener Katalog wird geholt";
  const anteil = k.gesamt ? Math.min(1, k.erledigt / k.gesamt) : null;
  if (k.schritt === "bauen") return { titel, text: "wird aufgebaut", anteil };
  return { titel, text: k.gesamt ? groesseVon(k.erledigt, k.gesamt) : k.erledigt ? groesse(k.erledigt) : "wird angefragt", anteil };
}

class Gutenberg {
  wort = $state("");
  sprache = $state("de");
  treffer = $state<Fundbuch[]>([]);
  gesamt = $state(0);
  seite = $state(1);
  weitere = $state(false);
  herkunft = $state<Trefferherkunft>("katalog");
  /** Vorschläge oder eine Seite werden geholt */
  laedt = $state(false);
  /** es gibt eine Liste (auch eine leere) zu dem, was dasteht */
  gesucht = $state(false);
  /** Gutendex wird gefragt, seit so vielen Sekunden */
  fragt = $state(false);
  sekunden = $state(0);
  katalog = $state<Katalogstand | null>(null);
  /** Aus einer Lücke hierher gesprungen: die Karte geht auf und kommt ins Bild */
  zeigen = $state(false);
  #gewaehlt = $state<ReadonlyMap<number, Fundbuch>>(new Map());

  zahl = $derived(this.#gewaehlt.size);
  alleGewaehlt = $derived(this.treffer.length > 0 && this.treffer.every((b) => this.#gewaehlt.has(b.gutenberg_id)));
  laeuft = $derived(annahme.gemeinfrei.laeuft);
  mehrereSeiten = $derived(this.seite > 1 || this.weitere);

  /** Jede Liste zählt; die Antwort auf eine ältere gilt nicht mehr */
  #lauf = 0;
  #tippen: ReturnType<typeof setTimeout> | undefined;
  #warten: AbortController | null = null;
  #uhr: ReturnType<typeof setInterval> | undefined;
  #katalogUhr: ReturnType<typeof setTimeout> | undefined;
  /** Das erste Holen des Katalogs kommt einmal von selbst; danach nur auf Wunsch */
  #vonSelbst = false;
  #katalogLief = false;
  #auftragstitel = "Eigenen Katalog holen";

  hat(id: number): boolean {
    return this.#gewaehlt.has(id);
  }

  // -- Vorschläge und Suche -------------------------------------------------------------------------------------------------

  /** Nach jedem Tastendruck: die Vorschläge kurz danach; eine wartende Suche bei Gutendex gilt der alten Frage und endet */
  tippe(): void {
    if (this.fragt) this.abbrechen();
    clearTimeout(this.#tippen);
    this.#tippen = setTimeout(() => void this.vorschlagen(1), VERZOEGERUNG_MS);
  }

  /** Vorschläge aus dem eigenen Katalog; ohne Wort keine Liste */
  async vorschlagen(seite = 1, herkunft: Trefferherkunft = "katalog"): Promise<void> {
    clearTimeout(this.#tippen);
    this.#tippen = undefined;
    const lauf = ++this.#lauf;
    if (!this.wort.trim()) {
      this.#zeige({ gesamt: 0, seite: 1, naechste: null, vorherige: null, buecher: [] }, "katalog", false);
      return;
    }
    this.laedt = true;
    try {
      const antwort = await schlageGemeinfreieVor(this.wort, this.sprache, seite);
      if (lauf === this.#lauf) this.#zeige(antwort, herkunft);
    } catch (e) {
      if (lauf === this.#lauf) melde.schlecht(e, "Keine Vorschläge");
    } finally {
      if (lauf === this.#lauf) this.laedt = false;
    }
  }

  /** Ausdrücklich bei Gutendex, mit großzügiger Geduld. Die Vorschläge stehen beim Warten unten und lassen sich schon holen;
   * antwortet Gutendex nicht, kommen die Treffer aus dem Katalog, und eine Meldung sagt warum. */
  async suche(seite = 1): Promise<void> {
    if (this.#tippen) void this.vorschlagen(1);
    this.#warten?.abort();
    const warten = new AbortController();
    this.#warten = warten;
    this.fragt = true;
    this.#uhrAn();
    try {
      const antwort = await sucheGemeinfreie(this.wort, this.sprache, seite, warten.signal);
      if (warten.signal.aborted) return;
      this.#lauf++;
      this.#zeige(antwort, antwort.herkunft === "katalog" ? "gestoert" : "gutendex");
      if (antwort.hinweis) melde.warn(antwort.hinweis);
    } catch (e) {
      if (!warten.signal.aborted) melde.warn(fehlertext(e));
    } finally {
      if (this.#warten === warten) this.#endeWarten();
    }
  }

  /** Nicht länger auf Gutendex warten; was dasteht, bleibt */
  abbrechen(): void {
    this.#warten?.abort();
    this.#endeWarten();
  }

  async blaettere(schritt: number): Promise<void> {
    const seite = Math.max(1, this.seite + schritt);
    if (this.herkunft === "gutendex") await this.suche(seite);
    else await this.vorschlagen(seite, this.herkunft);
  }

  #zeige(antwort: Fundliste, herkunft: Trefferherkunft, gesucht = true): void {
    this.treffer = antwort.buecher;
    this.gesamt = antwort.gesamt;
    this.seite = antwort.seite;
    this.weitere = !!antwort.naechste;
    this.herkunft = herkunft;
    this.gesucht = gesucht;
  }

  #uhrAn(): void {
    clearInterval(this.#uhr);
    const beginn = Date.now();
    this.sekunden = 0;
    this.#uhr = setInterval(() => (this.sekunden = Math.floor((Date.now() - beginn) / 1000)), UHR_MS);
  }

  #endeWarten(): void {
    this.#warten = null;
    this.fragt = false;
    clearInterval(this.#uhr);
  }

  /** Aus der Lücke einer Sammlung: Suche füllen, Vorschläge holen, die Karte zeigen */
  oeffnen(wort: string, sprache = ""): void {
    if (this.fragt) this.abbrechen();
    this.wort = wort;
    if (sprache) this.sprache = sprache;
    this.zeigen = true;
    void this.vorschlagen(1);
  }

  // -- Der eigene Katalog ---------------------------------------------------------------------------------------------------

  /** Beim Öffnen der Karte: der Stand; gibt es noch keinen Katalog, wird er einmal von selbst geholt */
  async oeffneKatalog(): Promise<void> {
    try {
      const k = await ladeKatalogstand();
      this.#katalogZeigen(k);
      if (!k.da && !k.laeuft && !this.#vonSelbst) {
        this.#vonSelbst = true;
        await this.holeKatalog();
      }
    } catch (e) {
      melde.schlecht(e, "Stand des eigenen Katalogs");
    }
  }

  /** Holen oder erneuern, als Auftrag; läuft es schon, bleibt es bei diesem Lauf */
  async holeKatalog(): Promise<void> {
    try {
      this.#katalogZeigen(await holeKatalog());
    } catch (e) {
      melde.schlecht(e, "Eigener Katalog nicht geholt");
    }
  }

  /** Den Stand übernehmen; solange er läuft, steht er unter Aufträge und wird nachgesehen, danach einmal mit dem Ergebnis */
  #katalogZeigen(k: Katalogstand): void {
    const lief = this.#katalogLief;
    this.katalog = k;
    this.#katalogLief = k.laeuft;
    clearTimeout(this.#katalogUhr);
    if (k.laeuft) {
      if (!lief) this.#auftragstitel = k.da ? "Eigenen Katalog erneuern" : "Eigenen Katalog holen";
      const a = katalogauftrag(k);
      auftraege.setze({ id: AUFTRAG, titel: this.#auftragstitel, text: a.text, anteil: a.anteil, laeuft: true, weg: "/import" });
      this.#katalogUhr = setTimeout(() => void this.#katalogNachsehen(), KATALOG_TAKT_MS);
      return;
    }
    if (!lief) return;
    if (k.grund) {
      auftraege.setze({ id: AUFTRAG, titel: this.#auftragstitel, text: `Gescheitert: ${k.grund}`, anteil: null, laeuft: false, weg: "/import" });
      melde.schlecht(`Eigener Katalog nicht geholt: ${k.grund}. Später erneut versuchen.`);
      return;
    }
    auftraege.setze({ id: AUFTRAG, titel: this.#auftragstitel, text: `Fertig, ${anzahl(k.anzahl, "Buch", "Bücher")}`, anteil: 1, laeuft: false, weg: "/import" });
    melde.gut(`Eigener Katalog ist da: ${anzahl(k.anzahl, "Buch", "Bücher")}`);
    if (this.wort.trim() && !this.fragt && this.herkunft === "katalog") void this.vorschlagen(1);
  }

  async #katalogNachsehen(): Promise<void> {
    try {
      this.#katalogZeigen(await ladeKatalogstand());
    } catch {
      this.#katalogUhr = setTimeout(() => void this.#katalogNachsehen(), KATALOG_TAKT_MS);   // ohne Antwort später noch einmal
    }
  }

  // -- Auswahl und Holen ----------------------------------------------------------------------------------------------------

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
    await uebernimmGemeinfreie([...this.#gewaehlt.values()].map(angabenAus));
    this.#gewaehlt = new Map();
    await annahme.auffrischen();
  }

  /** Geholtes, schon Vorhandenes und Gescheitertes aus der Liste nehmen; die Bücher bleiben */
  async zuruecksetzen(): Promise<void> {
    await auftraege.gemeinfreiAufraeumen();
  }
}

export const gutenberg = new Gutenberg();
