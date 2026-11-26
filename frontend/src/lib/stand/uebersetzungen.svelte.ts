// Übersetzungen unter Aufträge (BF-71): jede Fassung in Arbeit (läuft, Pause, Fehler) mit Anteil, Pause und Fortsetzen; ist
// eine fertig oder abgebrochen, steht sie einmal mit ihrem Ergebnis da, bis man sie ausblendet. Der Lauf rechnet am Server;
// die Schale fragt nach den Fassungen in Arbeit, schnell, solange eine läuft.
import { holeLaeufe, holeLaufstand, pausiereLauf, setzeLaufFort } from "../api/uebersetzung";
import { auftragstext, ergebnistext } from "../uebersetzung/texte";
import type { Laufeintrag } from "../uebersetzung/typen";
import { auftraege } from "./auftraege.svelte";
import { melde } from "./meldungen.svelte";
import { darfAbrufen } from "./abrufe";

const VORSILBE = "uebersetzung-";
const TAKT_AKTIV_MS = 3000;
const TAKT_RUHE_MS = 20_000;

export const auftragsweg = (buch: number): string => `/book/${buch}/uebersetzung`;

class Uebersetzungen {
  laeufe = $state<Laufeintrag[]>([]);
  #uhr: ReturnType<typeof setTimeout> | undefined;
  #an = false;
  /** Fassungen, die zuletzt in Arbeit waren: wer daraus verschwindet, zeigt sein Ergebnis */
  #inArbeit = new Map<number, Laufeintrag>();

  starte(): void {
    if (this.#an || !darfAbrufen("uebersetzungen")) return;
    this.#an = true;
    void this.#takt();
  }

  halte(): void {
    this.#an = false;
    clearTimeout(this.#uhr);
  }

  /** Fragt und plant die nächste Frage; läuft er doppelt an (Start auf der Buchseite), bleibt nur ein Takt übrig */
  async #takt(): Promise<void> {
    clearTimeout(this.#uhr);
    await this.auffrischen();
    if (!this.#an) return;
    clearTimeout(this.#uhr);
    this.#uhr = setTimeout(() => void this.#takt(), this.laeufe.some((l) => l.stand === "laeuft") ? TAKT_AKTIV_MS : TAKT_RUHE_MS);
  }

  /** Gleich nachfragen, etwa nach dem Start auf der Buchseite */
  async auffrischen(): Promise<void> {
    if (!darfAbrufen("uebersetzungen")) return;
    let laeufe: Laufeintrag[];
    try {
      laeufe = await holeLaeufe();
    } catch {
      return; // ohne Antwort bleibt der letzte Stand stehen
    }
    this.laeufe = laeufe;
    const jetzt = new Map(laeufe.map((l) => [l.id, l]));
    for (const [id, l] of this.#inArbeit) if (!jetzt.has(id)) void this.#ergebnis(l);
    this.#inArbeit = jetzt;
    for (const l of laeufe) this.#zeige(l);
  }

  /** Nach einem Start schneller fragen */
  angestossen(): void {
    if (this.#an) void this.#takt();
    else void this.auffrischen();
  }

  #zeige(l: Laufeintrag): void {
    auftraege.setze({
      id: `${VORSILBE}${l.id}`, titel: `Übersetzen: ${l.titel}`, text: auftragstext(l), anteil: l.kapitel_gesamt ? l.anteil : null,
      laeuft: l.stand === "laeuft", pausiert: l.stand !== "laeuft", weg: auftragsweg(l.buch_id),
      pause: () => void this.#tue(() => pausiereLauf(l.id), "Keine Pause"),
      fortsetzen: () => void this.#tue(() => setzeLaufFort(l.id), "Nicht fortgesetzt"),
    });
  }

  async #ergebnis(l: Laufeintrag): Promise<void> {
    try {
      const s = await holeLaufstand(l.id);
      auftraege.setze({ id: `${VORSILBE}${l.id}`, titel: `Übersetzen: ${l.titel}`, text: ergebnistext(s), anteil: null, laeuft: false, weg: auftragsweg(l.buch_id) });
    } catch {
      auftraege.entferne(`${VORSILBE}${l.id}`);
    }
  }

  async #tue(tun: () => Promise<unknown>, vorab: string): Promise<void> {
    try {
      await tun();
    } catch (e) {
      melde.schlecht(e, vorab);
    }
    await this.auffrischen();
  }
}

export const uebersetzungen = new Uebersetzungen();
