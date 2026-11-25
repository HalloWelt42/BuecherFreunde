// Abgleich der Autoren mit dem Lexikon: läuft als Auftrag weiter, auch wenn man die Seite verlässt
import { batchScanEvents, brecheBatchScanAb, type Abgleichereignis, type Autorvorschlag } from "../api/authors";
import { auftraege } from "./auftraege.svelte";
import { bestand } from "./bestand.svelte";

export interface Abgleichergebnis {
  autor: number;
  name: string;
  art: "gefunden" | "nicht_gefunden" | "fehler";
  vorschlag?: Autorvorschlag;
  uebernommen?: boolean;
  fehler?: string;
}

const AUFTRAG = "autoren";

class Autorenabgleich {
  nurOhneEintrag = $state(true);
  sichereUebernehmen = $state(true);
  laeuft = $state(false);
  fertig = $state(false);
  abgebrochen = $state(false);
  grund = $state("");
  stelle = $state(0);
  gesamt = $state(0);
  name = $state("");
  ergebnisse = $state<Abgleichergebnis[]>([]);

  gefunden = $derived(this.ergebnisse.filter((e) => e.art === "gefunden"));
  gescheitert = $derived(this.ergebnisse.filter((e) => e.art === "fehler"));
  ohne = $derived(this.ergebnisse.length - this.gefunden.length - this.gescheitert.length);
  anteil = $derived(this.gesamt ? this.stelle / this.gesamt : 0);
  zusammenfassung = $derived(`${this.gefunden.length} gefunden, ${this.ohne} ohne Eintrag${this.gescheitert.length ? `, ${this.gescheitert.length} gescheitert` : ""}`);

  #strom: { close: () => void } | null = null;

  starte(): void {
    if (this.laeuft) return;
    this.laeuft = true;
    this.fertig = false;
    this.abgebrochen = false;
    this.grund = "";
    this.stelle = 0;
    this.gesamt = 0;
    this.name = "";
    this.ergebnisse = [];
    this.#strom = batchScanEvents({ nurOhneWikidata: this.nurOhneEintrag, autoUebernehmen: this.sichereUebernehmen }, (e) => this.#nimm(e), () => this.#abgerissen());
    this.#zeige();
  }

  #nimm(e: Abgleichereignis): void {
    if (e.gesamt !== undefined) this.gesamt = e.gesamt;
    if (e.typ === "suche") {
      this.stelle = Math.max(0, (e.index ?? 1) - 1);
      this.name = e.name ?? "";
    } else if (e.typ === "gefunden" || e.typ === "nicht_gefunden" || e.typ === "fehler") {
      this.stelle = e.index ?? this.stelle;
      this.ergebnisse = [...this.ergebnisse, { autor: e.autor_id ?? 0, name: e.name ?? "", art: e.typ, vorschlag: e.vorschlag, uebernommen: e.uebernommen, fehler: e.fehler === undefined ? undefined : String(e.fehler) }];
    } else if (e.typ === "fertig" || e.typ === "abgebrochen") {
      this.abgebrochen = e.typ === "abgebrochen";
      this.#beende();
      return;
    }
    this.#zeige();
  }

  #abgerissen(): void {
    if (!this.laeuft) return;
    this.grund = this.gesamt ? "Die Verbindung ist abgerissen, der Abgleich steht." : "Der Abgleich startet nicht. Vielleicht läuft schon einer oder der Server antwortet nicht.";
    this.#beende();
  }

  async halte(): Promise<void> {
    if (!this.laeuft) return;
    this.abgebrochen = true;
    this.#beende();
    await brecheBatchScanAb().catch(() => {});
  }

  #beende(): void {
    this.#strom?.close();
    this.#strom = null;
    this.laeuft = false;
    this.fertig = true;
    this.name = "";
    this.#zeige();
    bestand.geaendert();
  }

  /** Ergebnis gelesen: aus der Ansicht und den Aufträgen nehmen */
  schliesse(): void {
    this.fertig = false;
    this.grund = "";
    this.ergebnisse = [];
    auftraege.entferne(AUFTRAG);
  }

  #zeige(): void {
    const stand = this.gesamt ? `${this.stelle} von ${this.gesamt}` : "wird vorbereitet";
    auftraege.setze({
      id: AUFTRAG,
      titel: "Autoren abgleichen",
      text: this.laeuft ? `${stand}${this.name ? `, ${this.name}` : ""}` : this.grund || `${this.abgebrochen ? "Angehalten" : "Fertig"}, ${this.zusammenfassung}`,
      anteil: this.laeuft && !this.gesamt ? null : this.laeuft ? this.anteil : this.grund ? null : 1,
      laeuft: this.laeuft,
      weg: "/authors",
      abbrechen: () => void this.halte(),
    });
  }
}

export const autorenabgleich = new Autorenabgleich();
