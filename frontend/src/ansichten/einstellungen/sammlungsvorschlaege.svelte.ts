// Sammlungen finden (BF-66): der Server sucht Reihen mit festen Regeln und prüft sie mit der lokalen KI; jeder Fund kommt
// als Vorschlag zum Anlegen, Anpassen oder Verwerfen. Der Suchlauf geht weiter, wenn man die Einstellungen verlässt; er steht
// unter Aufträge und meldet am Ende die Zahl der Funde.
import { ladeVorschlaege, legeVorschlagAn, sucheVorschlaege, verwirfVorschlag, vorschlagsstand } from "../../lib/api/collections";
import { anzahl } from "../../lib/format";
import { auftraege } from "../../lib/stand/auftraege.svelte";
import { bestand } from "../../lib/stand/bestand.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";
import type { Sammlungsvorschlag, Vorschlagsstand } from "../../lib/typen";

const TAKT_MS = 1500;
const AUFTRAG = "sammlungssuche";
const TITEL = "Sammlungen suchen";
const WEG = "/settings/regale";

/** So viele Umschläge zeigt ein Vorschlag, der Rest steht als "+n" daneben */
export const UMSCHLAEGE_HOECHSTENS = 9;

export function umschlagreihe<B>(buecher: B[], hoechstens = UMSCHLAEGE_HOECHSTENS): { gezeigt: B[]; rest: number } {
  return { gezeigt: buecher.slice(0, hoechstens), rest: Math.max(0, buecher.length - hoechstens) };
}

/** Fundwege der KI tragen ihr Zeichen, die der Regeln das Lineal */
export function wegSymbol(weg: string): string {
  return /^(die\s+)?ki\b/i.test(weg.trim()) ? "robot" : "ruler-combined";
}

/** Der Satz der KI, als solcher erkennbar */
export function kiSatz(ki: string): string {
  const satz = ki.trim();
  return !satz || /^(die\s+)?ki\b/i.test(satz) ? satz : `KI: ${satz}`;
}

/** Was nach einem Lauf gemeldet wird */
export function fundtext(gefunden: number): string {
  return gefunden ? `${anzahl(gefunden, "Vorschlag", "Vorschläge")} für Sammlungen gefunden` : "Keine neuen Sammlungen gefunden";
}

class Vorschlaege {
  liste = $state<Sammlungsvorschlag[]>([]);
  geladen = $state(false);
  fehler = $state("");
  stand = $state<Vorschlagsstand | null>(null);
  /** Was gerade angelegt oder verworfen wird */
  arbeitet = $state<ReadonlySet<number>>(new Set());
  #verfolgt = false;

  laeuft = $derived(!!this.stand?.laeuft);

  async laden(): Promise<void> {
    try {
      this.liste = await ladeVorschlaege();
      this.fehler = "";
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      this.geladen = true;
    }
    // Lief schon ein Suchlauf (aus einer früheren Sitzung), wird er weiter verfolgt
    await this.#holeStand();
    if (this.laeuft) void this.#verfolge();
  }

  async suche(): Promise<void> {
    if (this.laeuft) return;
    try {
      await sucheVorschlaege();
      this.stand = { laeuft: true, schritt: "", gefunden: 0, grund: "" };
      void this.#verfolge();
    } catch (e) {
      melde.schlecht(e, "Suche nicht begonnen");
    }
  }

  /** aenderung: eigener Name und nur die gewählten Bücher (Bücher anpassen) */
  async anlegen(v: Sammlungsvorschlag, aenderung?: { name: string; book_ids: number[] }): Promise<boolean> {
    return this.#erledige(v, async () => {
      await legeVorschlagAn(v.id, aenderung);
      melde.gut(`Sammlung ${aenderung?.name ?? v.name} angelegt`);
      bestand.geaendert();
    });
  }

  verwerfen(v: Sammlungsvorschlag): Promise<boolean> {
    return this.#erledige(v, async () => {
      await verwirfVorschlag(v.id);
      melde.info(`Vorschlag ${v.name} verworfen`);
    });
  }

  async #erledige(v: Sammlungsvorschlag, tun: () => Promise<void>): Promise<boolean> {
    this.arbeitet = new Set([...this.arbeitet, v.id]);
    try {
      await tun();
      this.liste = this.liste.filter((x) => x.id !== v.id);
      return true;
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
      return false;
    } finally {
      this.arbeitet = new Set([...this.arbeitet].filter((id) => id !== v.id));
    }
  }

  async #holeStand(): Promise<void> {
    try {
      this.stand = await vorschlagsstand();
    } catch {
      // ohne Antwort bleibt der letzte Stand stehen
    }
  }

  async #verfolge(): Promise<void> {
    if (this.#verfolgt) return;
    this.#verfolgt = true;
    try {
      while (this.laeuft) {
        auftraege.setze({ id: AUFTRAG, titel: TITEL, text: this.stand?.schritt || "Läuft", anteil: null, laeuft: true, weg: WEG });
        await new Promise((r) => setTimeout(r, TAKT_MS));
        await this.#holeStand();
      }
      const s = this.stand;
      const text = fundtext(s?.gefunden ?? 0);
      auftraege.setze({ id: AUFTRAG, titel: TITEL, text: s?.grund ? `${text}. ${s.grund}` : text, anteil: null, laeuft: false, weg: WEG });
      melde.gut(text);
      if (s?.grund) melde.warn(s.grund);
      await this.laden();
    } finally {
      this.#verfolgt = false;
    }
  }
}

export const vorschlaege = new Vorschlaege();
