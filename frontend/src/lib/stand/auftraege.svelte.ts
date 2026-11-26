// Was im Hintergrund läuft: Ergänzen der Bibliothek und eigene Aufträge einzelner Ansichten. Einlesen von Ordnern und
// gemeinfreie Bücher stehen in der einen Liste der Annahme (lib/stand/annahme.svelte.ts) und werden hier als Auftrag gezeigt.
import { brecheRescanAb, holeRescanStatus } from "../api/imports";
import { EINLESEN, ERLEDIGT, GEMEINFREI, WARTEND, type Sammelstand } from "../annahme/sammlung";
import { darfAbrufen } from "./abrufe";
import { annahme } from "./annahme.svelte";
import { bestand } from "./bestand.svelte";

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
  /** warum keine Angaben mehr ergänzt werden: alle Verzeichnisse machen Pause */
  grund?: string;
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
  /** Ein Lauf, der in Stapeln geht, macht Pause und geht später weiter (BF-69); pausiert zählt nicht als laufend */
  pausiert?: boolean;
  pause?: () => void;
  fortsetzen?: () => void;
}

const GEMEINFREI_AUFTRAG = "gemeinfrei";
const ERGAENZUNG: Ergaenzung = { laeuft: false, typ: "", gesamt: 0, fortschritt: 0, aktuelles_buch: "", cover_gefunden: 0, isbn_gefunden: 0, metadaten_aktualisiert: 0, volltext_extrahiert: 0, fehler: 0 };
const TAKT_AKTIV_MS = 1500;
const TAKT_RUHE_MS = 10_000;

/** Die gemeinfreie Übernahme als Auftrag im Kopf, wie ein eigener Auftrag einer Ansicht */
function gemeinfreiAuftrag(s: Sammelstand): EigenerAuftrag | null {
  if (!s.gesamt) return null;
  const neben = [s.da ? `${s.da} gab es schon` : "", s.gescheitert ? `${s.gescheitert} gescheitert` : ""].filter(Boolean);
  const jetzt = s.aktuell ? s.aktuell.name.replace(/\.(?:epub|txt)$/, "") : s.laeuft ? "" : "fertig";
  return { id: GEMEINFREI_AUFTRAG, titel: "Gemeinfreie Bücher holen", text: [`${s.erledigt} von ${s.gesamt}`, jetzt, ...neben].filter(Boolean).join(", "), anteil: s.erledigt / s.gesamt, laeuft: s.laeuft, weg: "/import" };
}

class Auftraege {
  ergaenzung = $state<Ergaenzung>(ERGAENZUNG);
  eigene = $state<EigenerAuftrag[]>([]);
  /** Ergebnis der letzten Ergänzung ausgeblendet */
  #gesehen = $state("");

  einlesenLaeuft = $derived(annahme.einlesen.laeuft);
  ergaenzungFertig = $derived(!this.ergaenzung.laeuft && this.ergaenzung.gesamt > 0 && this.#kennung() !== this.#gesehen);
  /** Eigene Aufträge der Ansichten und die gemeinfreie Übernahme */
  alleEigenen = $derived.by(() => {
    const g = gemeinfreiAuftrag(annahme.gemeinfrei);
    return g ? [...this.eigene, g] : this.eigene;
  });
  laufend = $derived((this.einlesenLaeuft ? 1 : 0) + (this.ergaenzung.laeuft ? 1 : 0) + this.alleEigenen.filter((e) => e.laeuft).length);

  #uhr: ReturnType<typeof setTimeout> | undefined;
  #an = false;
  #ergaenzungLief = false;

  #kennung(): string {
    const e = this.ergaenzung;
    return [e.typ, e.gesamt, e.cover_gefunden, e.isbn_gefunden, e.metadaten_aktualisiert, e.volltext_extrahiert, e.fehler].join("/");
  }

  starte(): void {
    if (this.#an || !darfAbrufen("ergaenzung")) return;
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
    this.#uhr = setTimeout(() => void this.#takt(), this.ergaenzung.laeuft ? TAKT_AKTIV_MS : TAKT_RUHE_MS);
  }

  /** Der Stand der Ergänzung; das Einlesen kommt mit dem Ereignisstrom der Annahme */
  async auffrischen(): Promise<void> {
    if (!darfAbrufen("ergaenzung")) return;
    try {
      const stand = await holeRescanStatus();
      if (!stand) return;
      this.ergaenzung = { ...ERGAENZUNG, ...stand };
      if (this.#ergaenzungLief && !this.ergaenzung.laeuft) bestand.geaendert();
      this.#ergaenzungLief = this.ergaenzung.laeuft;
    } catch {
      // ohne Antwort bleibt der letzte Stand stehen
    }
  }

  /** Fertig Eingelesenes ausblenden (die Bücher bleiben) und das Ergebnis der Ergänzung dazu */
  async bereinigen(): Promise<void> {
    this.#gesehen = this.#kennung();
    await annahme.raeumeAuf(EINLESEN, ERLEDIGT);
  }

  /** Wartende Dateien nicht mehr einlesen; was gerade läuft, läuft zu Ende */
  async einlesenAbbrechen(): Promise<void> {
    await annahme.raeumeAuf(EINLESEN, WARTEND);
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
    if (id === GEMEINFREI_AUFTRAG) void this.gemeinfreiAufraeumen();
    else this.eigene = this.eigene.filter((e) => e.id !== id);
  }

  /** Die gemeinfreie Übernahme aufräumen: Geholtes, schon Vorhandenes und Gescheitertes aus der Liste (Bücher bleiben) */
  async gemeinfreiAufraeumen(): Promise<void> {
    await annahme.raeumeAuf(GEMEINFREI, ERLEDIGT);
  }
}

export const auftraege = new Auftraege();
