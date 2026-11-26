// Einordnen (BF-69): der Server ordnet den Bestand in Stapeln ein, erst mit Regeln, dann mit der lokalen KI; jeder Fund kommt
// als Vorschlag. Du nimmst je Kategorie an oder lehnst ab: einzeln, angehakt oder alle. Der Lauf steht unter Aufträge, macht
// Pause und geht weiter, wenn man die Einstellungen verlässt.
import {
  beginneEinordnen, einordnenStand, lehneVorschlaegeAb, ladeVorschlaege, nimmVorschlaegeAn, pausiereEinordnen, setzeEinordnenFort, vorschlagsuebersicht,
} from "../../../lib/api/katalog";
import { anzahl, zahl } from "../../../lib/format";
import { auftraege } from "../../../lib/stand/auftraege.svelte";
import { bestand } from "../../../lib/stand/bestand.svelte";
import { melde } from "../../../lib/stand/meldungen.svelte";
import { frage } from "../../../lib/stand/rueckfrage.svelte";
import type { Katalogvorschlag, Laufstand } from "../../../lib/typen";

const TAKT_MS = 2000;
const JE_SEITE = 50;
const AUFTRAG = "katalog-einordnen";
const TITEL = "Einordnen";
const WEG = "/settings/katalog";

// Texte und Zahlen des Laufs

/** Lauf belegt: er läuft oder macht Pause */
export const laufBelegt = (l: Laufstand | null): boolean => !!l && (l.laeuft || l.pause);

export function laufkopf(l: Laufstand): string {
  if (l.pause) return "Einordnen macht Pause";
  return l.laeuft ? "Einordnen läuft" : "Einordnen fertig";
}

/** "Stapel 4 von 10, je 500 Titel": der Server zählt fertige Stapel, solange der Lauf belegt ist, steht der nächste */
export function stapeltext(l: Laufstand): string {
  if (!l.stapel_gesamt) return "";
  const jetzt = laufBelegt(l) && l.stapel < l.stapel_gesamt ? l.stapel + 1 : l.stapel;
  return `Stapel ${zahl(jetzt)} von ${zahl(l.stapel_gesamt)}, je ${zahl(l.stapel_groesse)} Titel`;
}

/** "Regeln: 1.874 Vorschläge, KI: 912 Vorschläge, 418 Bücher ohne Vorschlag" */
export function laufzahlen(l: Laufstand): string {
  return `Regeln: ${anzahl(l.regeln, "Vorschlag", "Vorschläge")}, KI: ${anzahl(l.ki, "Vorschlag", "Vorschläge")}, ${anzahl(l.ohne_vorschlag, "Buch", "Bücher")} ohne Vorschlag`;
}

export function laufanteil(l: Laufstand): number | null {
  return l.stapel_gesamt ? Math.min(1, l.stapel / l.stapel_gesamt) : null;
}

/** Gründe als knappe Zeilen: das Lineal für eine Regel, der Roboter für den Satz der KI */
const REGELGRUND = /^(Sachgruppe|Schlagwort|Wort im Titel|Titelwort|Verlag)\b/i;

export function grundzeilen(v: Pick<Katalogvorschlag, "gruende" | "quelle">): { symbol: string; text: string }[] {
  return v.gruende.map((g) => {
    const text = g.replace(/^KI:\s*/i, "").trim();
    const ki = v.quelle === "ki" || (v.quelle === "beide" && !REGELGRUND.test(g));
    return { symbol: ki ? "robot" : "ruler-combined", text };
  });
}

/** "auch: Elektronik, 88 %" */
export const auchText = (a: { name: string; sicherheit: number }): string => `auch: ${a.name}, ${zahl(a.sicherheit)} %`;

/** Nummern der Vorschläge, die mit diesen angenommen werden: die gewählten "auch" gehen mit */
export function mitAuch(vorschlaege: readonly Katalogvorschlag[], ids: readonly number[], auch: ReadonlySet<number>): number[] {
  const dazu = vorschlaege.filter((v) => ids.includes(v.id) && auch.has(v.id)).flatMap((v) => v.auch.map((a) => a.id));
  return [...new Set([...ids, ...dazu])];
}

class Einordnen {
  stand = $state<Laufstand | null>(null);
  /** Offene Vorschläge je Kategorie */
  uebersicht = $state<{ kategorie_id: number; anzahl: number }[]>([]);
  kategorie = $state<number | null>(null);
  vorschlaege = $state<Katalogvorschlag[]>([]);
  gesamt = $state(0);
  laedt = $state(false);
  geladen = $state(false);
  angehakt = $state<ReadonlySet<number>>(new Set());
  /** Vorschläge, deren "auch" beim Annehmen mitgeht */
  auch = $state<ReadonlySet<number>>(new Set());
  /** Was gerade angenommen oder abgelehnt wird */
  arbeitet = $state<ReadonlySet<number>>(new Set());
  #seite = 0;
  #lauf = 0;
  #verfolgt = false;

  belegt = $derived(laufBelegt(this.stand));
  /** Angehakte unter den geladenen, in ihrer Reihenfolge */
  gewaehlt = $derived(this.vorschlaege.filter((v) => this.angehakt.has(v.id)).map((v) => v.id));

  async laden(): Promise<void> {
    await Promise.all([this.#holeStand(), this.#holeUebersicht()]);
    this.geladen = true;
    if (this.kategorie === null || !this.uebersicht.some((u) => u.kategorie_id === this.kategorie)) this.kategorie = this.uebersicht[0]?.kategorie_id ?? null;
    await this.#ladeSeite(1);
    if (this.belegt) void this.#verfolge();
  }

  async starte(): Promise<void> {
    if (this.belegt) return;
    try {
      this.stand = await beginneEinordnen();
      void this.#verfolge();
    } catch (e) {
      melde.schlecht(e, "Einordnen nicht begonnen");
    }
  }

  pause = async (): Promise<void> => {
    try {
      this.stand = await pausiereEinordnen();
      this.#zeigeAuftrag();
    } catch (e) {
      melde.schlecht(e, "Keine Pause");
    }
  };

  fortsetzen = async (): Promise<void> => {
    try {
      this.stand = await setzeEinordnenFort();
      this.#zeigeAuftrag();
      void this.#verfolge();
    } catch (e) {
      melde.schlecht(e, "Nicht fortgesetzt");
    }
  };

  async waehle(kategorie: number): Promise<void> {
    if (kategorie === this.kategorie) return;
    this.kategorie = kategorie;
    await this.#ladeSeite(1);
  }

  async mehr(): Promise<void> {
    if (this.laedt || this.vorschlaege.length >= this.gesamt) return;
    await this.#ladeSeite(this.#seite + 1);
  }

  hake(id: number, an: boolean): void {
    this.angehakt = schalte(this.angehakt, id, an);
  }

  schalteAuch(id: number): void {
    this.auch = schalte(this.auch, id, !this.auch.has(id));
  }

  /** Einzelne oder die angehakten annehmen */
  async annehmen(ids: readonly number[]): Promise<void> {
    const alle = mitAuch(this.vorschlaege, ids, this.auch);
    await this.#erledige(ids, async () => {
      const { angenommen } = await nimmVorschlaegeAn({ ids: alle });
      melde.gut(`${anzahl(angenommen, "Vorschlag", "Vorschläge")} angenommen`);
    });
  }

  /** Alle offenen der gewählten Kategorie, auch die noch nicht geladenen */
  async annehmenAlle(): Promise<void> {
    const kategorie = this.kategorie;
    if (kategorie === null) return;
    await this.#erledige(this.vorschlaege.map((v) => v.id), async () => {
      const { angenommen } = await nimmVorschlaegeAn({ kategorie });
      melde.gut(`${anzahl(angenommen, "Vorschlag", "Vorschläge")} angenommen`);
    }, true);
  }

  async ablehnen(ids: readonly number[]): Promise<void> {
    if (ids.length > 1 && !(await frage({ titel: `${anzahl(ids.length, "Vorschlag", "Vorschläge")} ablehnen?`, folgen: ["Abgelehnte Vorschläge kommen nicht wieder.", "Die Bücher bleiben, wo sie stehen."], ja: "Ablehnen", symbol: "xmark" }))) return;
    await this.#erledige(ids, async () => {
      const { abgelehnt } = await lehneVorschlaegeAb([...ids]);
      melde.info(`${anzahl(abgelehnt, "Vorschlag", "Vorschläge")} abgelehnt`);
    });
  }

  async #erledige(ids: readonly number[], tun: () => Promise<void>, alle = false): Promise<void> {
    this.arbeitet = new Set([...this.arbeitet, ...ids]);
    try {
      await tun();
      this.vorschlaege = alle ? [] : this.vorschlaege.filter((v) => !ids.includes(v.id));
      this.gesamt = alle ? 0 : Math.max(0, this.gesamt - ids.length);
      for (const id of ids) this.angehakt = schalte(this.angehakt, id, false);
      bestand.geaendert();
      await this.#holeUebersicht();
      // Leer gewordene Kategorie: weiter zur nächsten; sonst Nachschub, wenn die Seite leer ist
      if (!this.uebersicht.some((u) => u.kategorie_id === this.kategorie)) {
        this.kategorie = this.uebersicht[0]?.kategorie_id ?? null;
        await this.#ladeSeite(1);
      } else if (!this.vorschlaege.length && this.gesamt) await this.#ladeSeite(1);
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
    } finally {
      this.arbeitet = new Set([...this.arbeitet].filter((id) => !ids.includes(id)));
    }
  }

  async #ladeSeite(seite: number): Promise<void> {
    const lauf = ++this.#lauf;
    const kategorie = this.kategorie;
    if (kategorie === null) {
      this.vorschlaege = [];
      this.gesamt = 0;
      return;
    }
    this.laedt = true;
    try {
      const antwort = await ladeVorschlaege(kategorie, seite, JE_SEITE);
      if (lauf !== this.#lauf) return;
      const neu = antwort.vorschlaege;
      this.vorschlaege = seite === 1 ? neu : [...this.vorschlaege, ...neu.filter((v) => !this.vorschlaege.some((x) => x.id === v.id))];
      this.gesamt = antwort.gesamt;
      this.#seite = seite;
      // Sichere Vorschläge stehen vorab angehakt
      if (seite === 1) this.angehakt = new Set(neu.filter((v) => v.vorab).map((v) => v.id));
      else this.angehakt = new Set([...this.angehakt, ...neu.filter((v) => v.vorab).map((v) => v.id)]);
    } catch (e) {
      if (lauf === this.#lauf) melde.schlecht(e, "Vorschläge nicht geladen");
    } finally {
      if (lauf === this.#lauf) this.laedt = false;
    }
  }

  async #holeStand(): Promise<void> {
    try {
      this.stand = await einordnenStand();
    } catch {
      // ohne Antwort bleibt der letzte Stand stehen
    }
  }

  async #holeUebersicht(): Promise<void> {
    try {
      this.uebersicht = (await vorschlagsuebersicht()).filter((u) => u.anzahl > 0).sort((a, b) => b.anzahl - a.anzahl);
    } catch {
      // bleibt wie zuletzt
    }
  }

  #zeigeAuftrag(): void {
    const l = this.stand;
    if (!l) return;
    const belegt = laufBelegt(l);
    const text = [belegt ? stapeltext(l) : laufzahlen(l), l.pause ? "Pause" : belegt ? l.schritt : "", l.grund].filter(Boolean).join(", ");
    auftraege.setze({
      id: AUFTRAG, titel: TITEL, text, anteil: belegt ? laufanteil(l) : null, laeuft: l.laeuft && !l.pause, pausiert: l.pause, weg: WEG,
      pause: this.pause, fortsetzen: this.fortsetzen,
    });
  }

  async #verfolge(): Promise<void> {
    if (this.#verfolgt) return;
    this.#verfolgt = true;
    let vorher = (this.stand?.regeln ?? 0) + (this.stand?.ki ?? 0);
    try {
      while (this.stand?.laeuft && !this.stand.pause) {
        this.#zeigeAuftrag();
        await new Promise((r) => setTimeout(r, TAKT_MS));
        await this.#holeStand();
        // Neue Vorschläge erscheinen schon während des Laufs
        const jetzt = (this.stand?.regeln ?? 0) + (this.stand?.ki ?? 0);
        if (jetzt !== vorher) {
          vorher = jetzt;
          await this.#holeUebersicht();
          if (this.kategorie === null && this.uebersicht.length) {
            this.kategorie = this.uebersicht[0].kategorie_id;
            await this.#ladeSeite(1);
          }
        }
      }
      this.#zeigeAuftrag();
      const s = this.stand;
      if (s && !s.laeuft && !s.pause) {
        melde.gut(`Einordnen fertig: ${laufzahlen(s)}`);
        if (s.grund) melde.warn(s.grund);
        await this.#holeUebersicht();
        await this.#ladeSeite(1);
      }
    } finally {
      this.#verfolgt = false;
    }
  }
}

function schalte(menge: ReadonlySet<number>, id: number, an: boolean): ReadonlySet<number> {
  const neu = new Set(menge);
  if (an) neu.add(id);
  else neu.delete(id);
  return neu;
}

export const einordnen = new Einordnen();
