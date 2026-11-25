// Was im Hintergrund läuft: Einlesen von Ordnern, Ergänzen der Bibliothek und eigene Aufträge einzelner Ansichten
import { get } from "../api/client";
import { bereinigeImportTasks, brecheImportAb, brecheRescanAb, holeRescanStatus } from "../api/imports";
import { bestand } from "./bestand.svelte";

export interface Einleseaufgabe {
  id: number;
  filename: string;
  status: "wartend" | "verarbeite" | "fertig" | "fehler" | "duplikat";
  progress_percent: number;
  current_step: string;
  error: string;
  book_id: number | null;
}

export interface Einlesezaehler {
  gesamt: number;
  wartend: number;
  verarbeite: number;
  fertig: number;
  fehler: number;
  duplikat: number;
}

export interface Ergaenzung {
  laeuft: boolean;
  typ: string;
  gesamt: number;
  fortschritt: number;
  aktuelles_buch: string;
  cover_gefunden: number;
  isbn_gefunden: number;
  metadaten_aktualisiert: number;
  volltext_extrahiert: number;
  fehler: number;
}

/** Auftrag einer Ansicht, etwa der Abgleich der Autoren */
export interface EigenerAuftrag {
  id: string;
  titel: string;
  text: string;
  /** null: Ende nicht absehbar */
  anteil: number | null;
  laeuft: boolean;
  weg?: string;
  abbrechen?: () => void;
}

const ZAEHLER: Einlesezaehler = { gesamt: 0, wartend: 0, verarbeite: 0, fertig: 0, fehler: 0, duplikat: 0 };
const ERGAENZUNG: Ergaenzung = { laeuft: false, typ: "", gesamt: 0, fortschritt: 0, aktuelles_buch: "", cover_gefunden: 0, isbn_gefunden: 0, metadaten_aktualisiert: 0, volltext_extrahiert: 0, fehler: 0 };
const TAKT_AKTIV_MS = 1500;
const TAKT_RUHE_MS = 10_000;

class Auftraege {
  aufgaben = $state<Einleseaufgabe[]>([]);
  zaehler = $state<Einlesezaehler>(ZAEHLER);
  ergaenzung = $state<Ergaenzung>(ERGAENZUNG);
  eigene = $state<EigenerAuftrag[]>([]);
  /** Ergebnis der letzten Ergänzung ausgeblendet */
  #gesehen = $state("");

  einlesenLaeuft = $derived(this.zaehler.wartend + this.zaehler.verarbeite > 0);
  ergaenzungFertig = $derived(!this.ergaenzung.laeuft && this.ergaenzung.gesamt > 0 && this.#kennung() !== this.#gesehen);
  laufend = $derived((this.einlesenLaeuft ? 1 : 0) + (this.ergaenzung.laeuft ? 1 : 0) + this.eigene.filter((e) => e.laeuft).length);

  #uhr: ReturnType<typeof setTimeout> | undefined;
  #an = false;
  #fertigZuvor: number | null = null;
  #ergaenzungLief = false;

  #kennung(): string {
    const e = this.ergaenzung;
    return [e.typ, e.gesamt, e.cover_gefunden, e.isbn_gefunden, e.metadaten_aktualisiert, e.volltext_extrahiert, e.fehler].join("/");
  }

  starte(): void {
    if (this.#an) return;
    this.#an = true;
    void this.#takt();
  }

  halte(): void {
    this.#an = false;
    clearTimeout(this.#uhr);
  }

  async #takt(): Promise<void> {
    await this.auffrischen();
    if (!this.#an) return;
    this.#uhr = setTimeout(() => void this.#takt(), this.einlesenLaeuft || this.ergaenzung.laeuft ? TAKT_AKTIV_MS : TAKT_RUHE_MS);
  }

  async auffrischen(): Promise<void> {
    const [einlesen, ergaenzen] = await Promise.allSettled([get("/api/import/status"), holeRescanStatus()]);
    if (einlesen.status === "fulfilled") this.#uebernimm(einlesen.value);
    if (ergaenzen.status === "fulfilled" && ergaenzen.value) {
      this.ergaenzung = { ...ERGAENZUNG, ...ergaenzen.value };
      if (this.#ergaenzungLief && !this.ergaenzung.laeuft) bestand.geaendert();
      this.#ergaenzungLief = this.ergaenzung.laeuft;
    }
  }

  #uebernimm(antwort: { aufgaben?: Einleseaufgabe[]; zaehler?: Einlesezaehler }): void {
    this.aufgaben = antwort.aufgaben ?? [];
    this.zaehler = { ...ZAEHLER, ...antwort.zaehler };
    if (this.#fertigZuvor !== null && this.zaehler.fertig > this.#fertigZuvor) bestand.geaendert();
    this.#fertigZuvor = this.zaehler.fertig;
  }

  async bereinigen(): Promise<void> {
    this.#uebernimm(await bereinigeImportTasks());
    this.#gesehen = this.#kennung();
  }

  async einlesenAbbrechen(): Promise<void> {
    await brecheImportAb();
    await this.auffrischen();
  }

  async ergaenzenAbbrechen(): Promise<void> {
    await brecheRescanAb();
    await this.auffrischen();
  }

  ergebnisAusblenden(): void {
    this.#gesehen = this.#kennung();
  }

  setze(auftrag: EigenerAuftrag): void {
    this.eigene = [...this.eigene.filter((e) => e.id !== auftrag.id), auftrag];
  }

  entferne(id: string): void {
    this.eigene = this.eigene.filter((e) => e.id !== id);
  }
}

export const auftraege = new Auftraege();
