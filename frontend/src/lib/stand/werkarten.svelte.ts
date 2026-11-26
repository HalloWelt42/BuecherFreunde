// Der Lauf, der die Art aller Werke bestimmt (BF-77), steht unter Aufträge wie die Aufträge der Ansichten: solange er läuft
// oder angehalten ist, danach einmal mit seinem Ergebnis zum Ausblenden. Er läuft am Server von selbst; die Schale fragt
// nach seinem Stand, schnell, solange er läuft.
import { einordnungsstand, setzeEinordnungFort } from "../api/einordnung";
import { anzahl, zahl } from "../format";
import type { Einordnungsstand } from "../typen";
import { darfAbrufen } from "./abrufe";
import { auftraege } from "./auftraege.svelte";
import { bestand } from "./bestand.svelte";
import { melde } from "./meldungen.svelte";

const AUFTRAG = "werkarten";
const TITEL = "Art der Werke bestimmen";
const TAKT_AKTIV_MS = 2000;
const TAKT_RUHE_MS = 15_000;

/** "9 von 12 eingeordnet: 7 nach Regel, 2 durch die KI, 3 offen" */
export function werkartentext(s: Einordnungsstand): string {
  const fertig = s.nach_regel + s.durch_ki;
  return `${zahl(fertig)} von ${anzahl(s.gesamt, "Werk", "Werken")} eingeordnet: ${zahl(s.nach_regel)} nach Regel, ${zahl(s.durch_ki)} durch die KI, ${zahl(s.offen)} offen`;
}

export function werkartenanteil(s: Einordnungsstand): number | null {
  return s.gesamt ? Math.min(1, (s.gesamt - s.offen) / s.gesamt) : null;
}

class Werkarten {
  stand = $state<Einordnungsstand | null>(null);
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #an = false;
  /** Lief er, seit die Schale fragt? Dann steht sein Ergebnis einmal unter Aufträge */
  #gesehen = false;

  starte(): void {
    if (this.#an || !darfAbrufen("werkarten")) return;
    this.#an = true;
    void this.#takt();
  }

  halte(): void {
    this.#an = false;
    clearTimeout(this.#uhr);
  }

  fortsetzen = async (): Promise<void> => {
    try {
      this.#zeige(await setzeEinordnungFort());
    } catch (e) {
      melde.schlecht(e, "Nicht fortgesetzt");
    }
  };

  async #takt(): Promise<void> {
    try {
      this.#zeige(await einordnungsstand());
    } catch {
      // ohne Antwort bleibt der letzte Stand stehen
    }
    if (!this.#an) return;
    this.#uhr = setTimeout(() => void this.#takt(), this.stand?.laeuft ? TAKT_AKTIV_MS : TAKT_RUHE_MS);
  }

  #zeige(s: Einordnungsstand): void {
    const vorher = this.stand;
    this.stand = s;
    const belegt = s.laeuft || s.angehalten;
    if (belegt) this.#gesehen = true;
    if (!belegt && !this.#gesehen) return;
    const text = [werkartentext(s), s.grund].filter(Boolean).join(". ");
    auftraege.setze({
      id: AUFTRAG, titel: TITEL, text, anteil: belegt ? werkartenanteil(s) : null, laeuft: s.laeuft, pausiert: s.angehalten,
      fortsetzen: this.fortsetzen,
    });
    // Ein fertiger Lauf ändert die Zahlen der Leiste
    if (vorher?.laeuft && !s.laeuft) bestand.geaendert();
    if (!belegt) this.#gesehen = false;
  }
}

export const werkarten = new Werkarten();
