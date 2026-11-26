// Zustand der Vorschau (BF-80): die Vorschau vom Server, Filter und Auswahl, Ändern, Übernehmen, Verwerfen. Die Folgen
// des Verwerfens kommen vom Server, erst ein Ja in der Rückfrage verwirft.
import { aendereVorschau, ladeVorschau, uebernimmVorschau, verwerffolgen, verwirfVorschau } from "../../../lib/api/annahme";
import { ApiError } from "../../../lib/api/client";
import { aenderbar, filterzahlen, inDerListe, kopfzeile, nichtUebernommen, passt, verwerfliste, verwerfsaetze, vonHand, type Vorschaufilter } from "../../../lib/annahme/vorschau";
import type { Felderaenderung, Vorschau, Vorschauzeile } from "../../../lib/annahme/vorschautypen";
import { annahme } from "../../../lib/stand/annahme.svelte";
import { bestand } from "../../../lib/stand/bestand.svelte";
import { melde } from "../../../lib/stand/meldungen.svelte";
import { frage } from "../../../lib/stand/rueckfrage.svelte";

/** Solange die KI prüft oder noch etwas läuft, fragt die Vorschau so oft nach */
const NACHSEHEN_MS = 4000;

export class Vorschaustand {
  vorschau = $state<Vorschau | null>(null);
  fehler = $state("");
  filter = $state<Vorschaufilter>("alle");
  gewaehlt = $state<number[]>([]);
  /** Übernehmen, Verwerfen oder Ändern läuft gerade */
  arbeitet = $state(false);
  uebernimmt = $state(false);

  zeilen = $derived<Vorschauzeile[]>(this.vorschau?.zeilen ?? []);
  liste = $derived(this.zeilen.filter((z) => inDerListe(z) && passt(z, this.filter)));
  rest = $derived(this.zeilen.filter(nichtUebernommen));
  zahlen = $derived(filterzahlen(this.zeilen));
  offen = $derived(this.vorschau?.stand === "offen");
  /** Was sich in der gezeigten Liste anhaken lässt */
  waehlbar = $derived(this.offen ? this.liste.filter((z) => aenderbar(z) && !!z.felder) : []);
  auswahl = $derived(this.zeilen.filter((z) => this.gewaehlt.includes(z.id) && aenderbar(z) && !!z.felder));
  /** Die Werke dieser Vorschau, zu denen Material oder ein weiteres Format gehören kann */
  werke = $derived(this.zeilen.filter((z) => z.rolle === "buch" && z.felder?.doppel.wahl !== "format"));
  kopf = $derived(this.vorschau ? kopfzeile(this.vorschau) : "");
  /** Dateien dieses Browsers, die noch nicht beim Server sind (Prüfsumme, erste Teile) */
  unterwegs = $derived(annahme.hochladungen.filter((h) => h.ziel.art === "vorschau" && h.ziel.vorschau === this.id && h.lage !== "beim_server" && !this.zeilen.some((z) => z.id === h.eintrag?.id)));

  #lauf = 0;

  constructor(public readonly id: string) {}

  async laden(): Promise<void> {
    const lauf = ++this.#lauf;
    try {
      const v = await ladeVorschau(this.id);
      if (lauf !== this.#lauf) return;
      this.#nimm(v);
      this.fehler = "";
    } catch (e) {
      if (lauf === this.#lauf) this.fehler = e instanceof Error ? e.message : String(e);
    }
  }

  #nimm(v: Vorschau): void {
    this.vorschau = v;
    const noch = new Set(v.zeilen.filter((z) => aenderbar(z) && z.felder).map((z) => z.id));
    if (this.gewaehlt.some((id) => !noch.has(id))) this.gewaehlt = this.gewaehlt.filter((id) => noch.has(id));
  }

  /** Woran man sieht, dass sich am Server etwas an dieser Vorschau getan hat (Ereignisstrom der Annahme) */
  get kennung(): string {
    const kurz = annahme.vorschauen.find((v) => v.id === this.id);
    const eigene = annahme.eintraege.filter((e) => e.vorschau === this.id).map((e) => `${e.id}:${e.stand}:${e.geaendert_am}`);
    return [kurz ? `${kurz.geaendert_am}/${kurz.warten}/${kurz.laeuft}/${kurz.ki}` : "", ...eigene].join("|");
  }

  /** Nachsehen, solange die KI prüft oder etwas läuft; liefert das Aufräumen */
  nachsehen(): () => void {
    const z = this.vorschau?.zaehler;
    if (!this.offen || !z || (!z.ki && !z.laeuft && !this.unterwegs.length)) return () => {};
    const uhr = setTimeout(() => void this.laden(), NACHSEHEN_MS);
    return () => clearTimeout(uhr);
  }

  waehle(id: number, an: boolean): void {
    this.gewaehlt = an ? [...new Set([...this.gewaehlt, id])] : this.gewaehlt.filter((x) => x !== id);
  }

  alle(an: boolean): void {
    this.gewaehlt = an ? this.waehlbar.map((z) => z.id) : [];
  }

  aufheben(): void {
    this.gewaehlt = [];
  }

  /** Felder setzen; geht eine Datei nicht, ändert sich keine, der Grund kommt als Meldung */
  async aendere(ids: number[], felder: Felderaenderung): Promise<boolean> {
    if (!ids.length) return false;
    this.arbeitet = true;
    try {
      this.#nimm(await aendereVorschau(this.id, ids, felder));
      return true;
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
      if (e instanceof ApiError && e.status === 409) void this.laden();
      return false;
    } finally {
      this.arbeitet = false;
    }
  }

  /** Übernimmt alle wartenden; was weggelassen oder nicht übernommen wird, bleibt im Eingang, ein Hinweis nennt es */
  async uebernimm(): Promise<void> {
    this.arbeitet = this.uebernimmt = true;
    try {
      const { weiter, vorschau } = await uebernimmVorschau(this.id);
      this.#nimm(vorschau);
      this.gewaehlt = [];
      const satz = `${weiter} ${weiter === 1 ? "Datei geht" : "Dateien gehen"} ins Regal.`;
      melde.gut(vorschau.hinweis ? `${satz} ${vorschau.hinweis}.` : satz);
      bestand.geaendert();
      void annahme.auffrischen();
    } catch (e) {
      melde.schlecht(e, "Nicht übernommen");
    } finally {
      this.arbeitet = this.uebernimmt = false;
    }
  }

  /** Fragt mit allen Dateien und ihrer Wirkung nach; verwirft erst nach dem Ja und nur, wenn sich seither nichts geändert hat */
  async verwirf(): Promise<boolean> {
    const v = this.vorschau;
    if (!v) return false;
    this.arbeitet = true;
    try {
      const folgen = await verwerffolgen(this.id);
      const endgueltig = folgen.endgueltig > 0;
      const ja = await frage({ titel: "Vorschau verwerfen?", text: kopfzeile(v), folgen: verwerfsaetze(folgen, vonHand(v)), liste: verwerfliste(folgen), ja: endgueltig ? "Endgültig verwerfen" : "Verwerfen" });
      if (!ja) return false;
      const { verworfen, vorschau } = await verwirfVorschau(this.id, folgen.stand);
      this.#nimm(vorschau);
      melde.gut(`${verworfen} ${verworfen === 1 ? "Datei" : "Dateien"} verworfen.`);
      void annahme.auffrischen();
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        melde.info("Inzwischen hat sich etwas geändert. Bitte die Folgen noch einmal ansehen.");
        void this.laden();
      } else melde.schlecht(e, "Nicht verworfen");
      return false;
    } finally {
      this.arbeitet = false;
    }
  }
}
