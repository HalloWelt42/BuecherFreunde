// Hochladen in Teilen, fortsetzbar: höchstens zwei Dateien zugleich, nach einem Abriss weiter am Stand des Servers.
// Ohne Oberfläche; Dienst, Prüfsumme und Wartezeiten kommen von außen und lassen sich im Test ersetzen.
import { AndererStand, OhneVerbindung, type AnnahmeDienst, type AnnahmeEintrag, type Hochladung, type Lage } from "./typen";

type Pruefsumme = (datei: Blob, fortschritt: (anteil: number) => void, abbruch: AbortSignal) => Promise<string>;

export interface HochladerOptionen {
  gleichzeitig?: number;
  /** Wartezeiten nach einem Abriss, die letzte gilt für alle weiteren Versuche */
  pausenMs?: number[];
  warte?: (ms: number) => Promise<void>;
}

interface Arbeit {
  ansicht: Hochladung;
  datei: File;
  anreichern: boolean;
  abbruch: AbortController | null;
  wecke: (() => void) | null;
  versuche: number;
}

const HOCHZULADEN = ["wartet", "laedt", "angehalten"];
const TEIL_VORGABE = 4 * 1024 * 1024;

export class Hochlader {
  #arbeiten = new Map<string, Arbeit>();
  #reihe: string[] = [];
  #laufend = 0;
  #naechste = 1;
  #zuhoerer = new Set<(liste: Hochladung[]) => void>();
  #dienst: AnnahmeDienst;
  #pruefsumme: Pruefsumme;
  #gleichzeitig: number;
  #pausen: number[];
  #warte: (ms: number) => Promise<void>;

  constructor(dienst: AnnahmeDienst, pruefsumme: Pruefsumme, optionen: HochladerOptionen = {}) {
    this.#dienst = dienst;
    this.#pruefsumme = pruefsumme;
    this.#gleichzeitig = optionen.gleichzeitig ?? 2;
    this.#pausen = optionen.pausenMs ?? [1000, 3000, 8000, 20000];
    this.#warte = optionen.warte ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  }

  get liste(): Hochladung[] {
    return [...this.#arbeiten.values()].map((a) => ({ ...a.ansicht }));
  }

  /** Läuft noch etwas, das ein Neuladen der Seite abbrechen würde? */
  get laeuft(): boolean {
    return [...this.#arbeiten.values()].some((a) => ["ansteht", "prueft", "laedt", "ohne_verbindung"].includes(a.ansicht.lage));
  }

  beiAenderung(tun: (liste: Hochladung[]) => void): () => void {
    this.#zuhoerer.add(tun);
    return () => this.#zuhoerer.delete(tun);
  }

  fuegeHinzu(dateien: Iterable<File>, anreichern = false): void {
    for (const datei of dateien) {
      const schon = [...this.#arbeiten.values()].find((a) => a.datei.name === datei.name && a.datei.size === datei.size && a.ansicht.lage !== "beim_server");
      if (schon) {
        this.weiter(schon.ansicht.schluessel);
        continue;
      }
      const schluessel = `datei-${this.#naechste++}`;
      const ansicht: Hochladung = { schluessel, name: datei.name, groesse: datei.size, lage: "ansteht", anteil: 0, gesendet: 0, text: "Wartet, bis ein Platz frei ist", eintrag: null };
      this.#arbeiten.set(schluessel, { ansicht, datei, anreichern, abbruch: null, wecke: null, versuche: 0 });
      this.#reihe.push(schluessel);
    }
    this.#melde();
    this.#starte();
  }

  anhalten(schluessel: string): void {
    const a = this.#arbeiten.get(schluessel);
    if (!a || !["ansteht", "prueft", "laedt", "ohne_verbindung"].includes(a.ansicht.lage)) return;
    this.#reihe = this.#reihe.filter((s) => s !== schluessel);
    this.#setze(a, "angehalten", "Angehalten, geht an dieser Stelle weiter");
    a.abbruch?.abort();
    a.wecke?.();
  }

  weiter(schluessel: string): void {
    const a = this.#arbeiten.get(schluessel);
    if (!a) return;
    if (a.ansicht.lage === "ohne_verbindung") {
      a.versuche = 0;
      a.wecke?.();
    } else if (a.ansicht.lage === "angehalten" || a.ansicht.lage === "fehler") {
      this.#setze(a, "ansteht", "Wartet, bis ein Platz frei ist");
      if (!this.#reihe.includes(schluessel)) this.#reihe.push(schluessel);
      this.#starte();
    }
  }

  entferne(schluessel: string): void {
    this.anhalten(schluessel);
    this.#reihe = this.#reihe.filter((s) => s !== schluessel);
    this.#arbeiten.delete(schluessel);
    this.#melde();
  }

  /** Das Netz ist wieder da: nicht erst die Pause abwarten */
  verbindungDa(): void {
    for (const a of this.#arbeiten.values()) if (a.ansicht.lage === "ohne_verbindung") this.weiter(a.ansicht.schluessel);
  }

  #melde(): void {
    const liste = this.liste;
    for (const tun of this.#zuhoerer) tun(liste);
  }

  #setze(a: Arbeit, lage: Lage, text: string): void {
    a.ansicht.lage = lage;
    a.ansicht.text = text;
    this.#melde();
  }

  #starte(): void {
    while (this.#laufend < this.#gleichzeitig && this.#reihe.length) {
      const a = this.#arbeiten.get(this.#reihe.shift()!);
      if (!a) continue;
      this.#laufend++;
      void this.#bearbeite(a).finally(() => {
        this.#laufend--;
        this.#starte();
      });
    }
  }

  async #bearbeite(a: Arbeit): Promise<void> {
    const abbruch = new AbortController();
    a.abbruch = abbruch;
    while (!abbruch.signal.aborted) {
      try {
        const eintrag = a.ansicht.eintrag ? await this.#dienst.stand(a.ansicht.eintrag.id) : await this.#anlegen(a, abbruch.signal);
        if (abbruch.signal.aborted) return;
        await this.#sende(a, eintrag, abbruch.signal);
        return;
      } catch (grund) {
        if (abbruch.signal.aborted) return;
        if (!(grund instanceof OhneVerbindung)) {
          this.#setze(a, "fehler", grund instanceof Error ? grund.message : String(grund));
          return;
        }
        await this.#pause(a);
      }
    }
  }

  async #anlegen(a: Arbeit, abbruch: AbortSignal): Promise<AnnahmeEintrag> {
    this.#setze(a, "prueft", "Prüfsumme wird gebildet");
    const sha256 = await this.#pruefsumme(a.datei, (anteil) => {
      a.ansicht.anteil = anteil;
      this.#melde();
    }, abbruch);
    abbruch.throwIfAborted();
    const eintrag = await this.#dienst.anlegen({ name: a.datei.name, groesse: a.datei.size, sha256, anreichern: a.anreichern });
    a.ansicht.eintrag = eintrag;
    return eintrag;
  }

  async #sende(a: Arbeit, anfang: AnnahmeEintrag, abbruch: AbortSignal): Promise<void> {
    let eintrag = anfang;
    let ab = eintrag.empfangen;
    while (HOCHZULADEN.includes(eintrag.stand) && ab < a.datei.size) {
      this.#fortschritt(a, eintrag, ab);
      try {
        eintrag = await this.#dienst.teil(eintrag.id, ab, a.datei.slice(ab, ab + (eintrag.teil_groesse || TEIL_VORGABE)), abbruch);
        ab = this.#weiterAb(ab, eintrag.empfangen, HOCHZULADEN.includes(eintrag.stand));
        a.versuche = 0;
      } catch (grund) {
        if (!(grund instanceof AndererStand)) throw grund;
        ab = this.#weiterAb(ab, grund.empfangen, true);
      }
      if (abbruch.aborted) return;
    }
    a.ansicht.eintrag = eintrag;
    a.ansicht.gesendet = a.datei.size;
    this.#setze(a, "beim_server", eintrag.text);
  }

  /** Rückt der Server nicht weiter, wird nicht sofort noch einmal geschickt, sondern erst nach einer Pause */
  #weiterAb(bisher: number, stand: number, offen: boolean): number {
    if (offen && stand === bisher) throw new OhneVerbindung("Der Server nimmt gerade nichts an");
    return stand;
  }

  #fortschritt(a: Arbeit, eintrag: AnnahmeEintrag, ab: number): void {
    a.ansicht.eintrag = eintrag;
    a.ansicht.gesendet = ab;
    a.ansicht.anteil = a.datei.size ? ab / a.datei.size : 0;
    this.#setze(a, "laedt", "Wird in der Kellerwolke abgelegt");
  }

  async #pause(a: Arbeit): Promise<void> {
    const ms = this.#pausen[Math.min(a.versuche, this.#pausen.length - 1)];
    a.versuche++;
    const prozent = Math.floor(a.ansicht.anteil * 100);
    this.#setze(a, "ohne_verbindung", a.ansicht.eintrag ? `Verbindung weg bei ${prozent} %. Geht von selbst an dieser Stelle weiter.` : "Der Server antwortet nicht. Geht von selbst weiter.");
    await Promise.race([this.#warte(ms), new Promise<void>((r) => (a.wecke = r))]);
    a.wecke = null;
  }
}
