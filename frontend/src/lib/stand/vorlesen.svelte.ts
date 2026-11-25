// Vorlesen: welche Stimmen es gibt, welche gilt, was gerade klingt. Ist ein Sprechdienst angeschlossen, spricht nur er; sonst die
// Stimmen des Geräts. Beide hinter derselben Schnittstelle (lib/vorlesen).
import { ladeDienststimmen, type Dienststimmen } from "../api/vorlesen";
import { lies as gemerkt, merke } from "../speicher";
import { Dienstvorleser } from "../vorlesen/dienst";
import { geraetDa, geraetestimmen, Geraetevorleser } from "../vorlesen/geraet";
import type { Stimme, Vorleser } from "../vorlesen/typen";
import { melde } from "./meldungen.svelte";
import { anschluesse } from "./anschluesse.svelte";

const SCHLUESSEL = "vorlesen.stimme";
const PROBE = "So klingt diese Stimme beim Vorlesen.";
const GRUPPEN = { eigene: "Eigene Stimmen", weitere: "Weitere Stimmen", eingebaut: "Eingebaute Stimmen" };

class Vorlesestand {
  aktiv = $state(false);
  wartet = $state(false);
  was = $state("");
  #gewaehlt = $state(gemerkt(SCHLUESSEL));
  #dienst = $state<Dienststimmen | null>(null);
  #geraet = $state<Stimme[]>([]);
  #gefragt = false;
  #vorleser: Record<string, Vorleser> = { dienst: new Dienstvorleser(), geraet: new Geraetevorleser() };
  #spricht: Vorleser | null = null;

  stimmen = $derived<Stimme[]>(
    anschluesse.jetzt.vorlesen
      ? this.#dienst?.da
        ? [{ id: "dienst:", name: "Vorgabe des Sprechdienstes", gruppe: "Sprechdienst" }, ...this.#dienst.stimmen.map((s) => ({ id: `dienst:${s.id}`, name: s.name, gruppe: GRUPPEN[s.gruppe] }))]
        : []
      : this.#geraet,
  );

  /** Die Stimme, die gilt: die gewählte, solange es sie gibt, sonst die erste */
  stimme = $derived(this.stimmen.some((s) => s.id === this.#gewaehlt) ? this.#gewaehlt : (this.stimmen[0]?.id ?? ""));
  hinweis = $derived(this.#dienst?.hinweis ?? "");

  gruppen = $derived.by(() => {
    const aus = new Map<string, [string, string][]>();
    for (const s of this.stimmen) aus.set(s.gruppe, [...(aus.get(s.gruppe) ?? []), [s.id, s.name]]);
    return [...aus];
  });

  /** Einmal je Seite; die Stimmen des Geräts melden manche Browser erst später. */
  pruefe(): void {
    if (this.#gefragt) return;
    this.#gefragt = true;
    if (anschluesse.jetzt.vorlesen) {
      ladeDienststimmen().then((d) => (this.#dienst = d)).catch(() => (this.#gefragt = false));
      return;
    }
    if (!geraetDa()) return;
    this.#geraet = geraetestimmen();
    speechSynthesis.addEventListener?.("voiceschanged", () => (this.#geraet = geraetestimmen()));
  }

  waehle(id: string): void {
    this.halt();
    this.#gewaehlt = id;
    merke(SCHLUESSEL, id);
  }

  #teile(): [Vorleser | undefined, string] {
    const trenner = this.stimme.indexOf(":");
    return [this.#vorleser[this.stimme.slice(0, trenner)], this.stimme.slice(trenner + 1)];
  }

  /** Noch im Tippen rufen, wenn der Text erst danach geholt wird. */
  entsperre(): void {
    this.#teile()[0]?.entsperre();
  }

  lies(text: string, was: string): void {
    this.halt();
    const [vorleser, stimme] = this.#teile();
    if (!text.trim()) return;
    if (!vorleser) return void melde.warn(this.hinweis || "Hier gibt es keine Stimme zum Vorlesen");
    this.#spricht = vorleser;
    Object.assign(this, { aktiv: true, wartet: true, was });
    const gilt = () => this.#spricht === vorleser;
    vorleser.lies(text.trim(), stimme, {
      klingt: () => gilt() && (this.wartet = false),
      wartet: () => gilt() && (this.wartet = true),
      ende: () => gilt() && this.#fertig(),
      fehler: (grund) => {
        if (!gilt()) return;
        this.#fertig();
        melde.warn(grund);
      },
    });
  }

  probe(): void {
    this.lies(PROBE, "Probe");
  }

  halt(): void {
    this.#spricht?.halt();
    this.#fertig();
  }

  #fertig(): void {
    this.#spricht = null;
    Object.assign(this, { aktiv: false, wartet: false, was: "" });
  }
}

export const vorlesen = new Vorlesestand();
