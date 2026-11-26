// Die Lesezeit eines Kindes: gezählt wird, solange der Kinderleser offen und zu sehen ist und das Kind liest (es bedient ihn
// oder es wird vorgelesen); gemeldet im Takt an POST /api/familie/lesezeit. Der Server rechnet und entscheidet: seine Antwort
// sagt, was bleibt, ob Ruhezeit ist und ab wann der sanfte Hinweis kommt. Hier wird nur bis zur nächsten Antwort weitergezählt.
import type { Lesezeitstand } from "./typen";

/** So oft geht die gelesene Zeit an den Server */
export const TAKT_S = 30;
/** Ohne Bedienung und ohne Vorlesen zählt es nach so vielen Sekunden nicht mehr: das Kind ist weg */
export const LEERLAUF_S = 180;

export interface Lesezeitgriffe {
  melde(sekunden: number, vorlesen: boolean, beimGehen: boolean): Promise<Lesezeitstand>;
  /** Millisekunden, wie Date.now */
  jetzt(): number;
  sichtbar(): boolean;
}

export const OHNE_GRENZE: Lesezeitstand = { heute_s: 0, rest_s: null, ruht: false, ruhe_bis: null, ruhe_ab: null, hinweis_ab_s: null };

/** Was heute noch bleibt, mit den noch nicht gemeldeten Sekunden; null: ohne Grenze */
export function restVon(stand: Lesezeitstand, offen: number): number | null {
  return stand.rest_s === null ? null : Math.max(0, stand.rest_s - offen);
}

/** Ist die Lesezeit um oder Ruhezeit? Das sagt nur der Server. */
export const faelligVon = (stand: Lesezeitstand): boolean => stand.ruht || (stand.rest_s !== null && stand.rest_s <= 0);

/** Kommt der sanfte Hinweis? Nur in Stufen mit Hinweis und solange noch Zeit bleibt */
export function hinweisVon(stand: Lesezeitstand, rest: number | null): boolean {
  return stand.hinweis_ab_s !== null && rest !== null && rest > 0 && rest <= stand.hinweis_ab_s && !stand.ruht;
}

/** Der nächste Zeitpunkt zu "07:00" oder ein Zeitpunkt selbst; null, wenn nichts zu lesen ist */
function zeitpunkt(angabe: string | null, jetzt: Date): Date | null {
  if (!angabe) return null;
  const uhrzeit = /^(\d{1,2}):(\d{2})$/.exec(angabe);
  if (uhrzeit) {
    const heute = new Date(jetzt.getFullYear(), jetzt.getMonth(), jetzt.getDate(), Number(uhrzeit[1]), Number(uhrzeit[2]));
    return heute.getTime() > jetzt.getTime() ? heute : new Date(heute.getTime() + 86_400_000);
  }
  const d = new Date(angabe);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Wann es weitergeht, für Kinder gesagt: "Morgen ab 7 Uhr", "Ab 15:30 Uhr"; ohne Angabe "Morgen" */
export function weiterAb(ruheBis: string | null, jetzt: Date): string {
  const bis = zeitpunkt(ruheBis, jetzt);
  if (!bis) return "Morgen";
  const uhr = bis.getMinutes() ? `${bis.getHours()}:${String(bis.getMinutes()).padStart(2, "0")} Uhr` : `${bis.getHours()} Uhr`;
  const tag = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const tage = Math.round((tag(bis) - tag(jetzt)) / 86_400_000);
  if (tage <= 0) return `Ab ${uhr}`;
  if (tage === 1) return `Morgen ab ${uhr}`;
  return `Am ${bis.toLocaleDateString("de-DE", { weekday: "long" })} ab ${uhr}`;
}

export class Lesezeituhr {
  stand = $state<Lesezeitstand>(OHNE_GRENZE);
  /** Gezählt, aber noch nicht gemeldet */
  offen = $state(0);
  /** Der Kinderleser ist offen */
  liest = false;
  /** Es wird gerade vorgelesen */
  vorliest = false;
  #offenVorlesen = false;
  #regung = 0;
  #sendet = false;

  rest = $derived(restVon(this.stand, this.offen));
  faellig = $derived(faelligVon(this.stand));
  hinweis = $derived(hinweisVon(this.stand, this.rest));

  constructor(private griffe: Lesezeitgriffe, stand: Lesezeitstand = OHNE_GRENZE) {
    this.stand = stand;
    this.#regung = griffe.jetzt();
  }

  /** Ein neuer Stand vom Server (GET /api/familie/ich); Ungemeldetes bleibt ungemeldet */
  uebernimm(stand: Lesezeitstand): void {
    this.stand = stand;
  }

  /** Das Kind hat etwas getan */
  regung(): void {
    this.#regung = this.griffe.jetzt();
  }

  /** Zählt es gerade? */
  get zaehlt(): boolean {
    if (!this.liest || !this.griffe.sichtbar()) return false;
    return this.vorliest || this.griffe.jetzt() - this.#regung < LEERLAUF_S * 1000;
  }

  /** Eine Sekunde ist vergangen */
  schritt(): void {
    if (!this.zaehlt) return;
    // Jede Meldung ist entweder Lesen oder Vorlesen
    if (this.offen > 0 && this.#offenVorlesen !== this.vorliest) void this.melde();
    this.#offenVorlesen = this.vorliest;
    this.offen++;
    const rest = this.rest;
    if (this.offen >= TAKT_S || (rest !== null && rest <= 0)) void this.melde();
  }

  /** Das Gezählte an den Server; beimGehen: auch noch, wenn die Seite gerade zugeht */
  async melde(beimGehen = false): Promise<void> {
    const sekunden = this.offen;
    if (this.#sendet || sekunden <= 0) return;
    this.#sendet = true;
    try {
      const stand = await this.griffe.melde(sekunden, this.#offenVorlesen, beimGehen);
      this.offen = Math.max(0, this.offen - sekunden);
      this.stand = stand;
    } catch {
      // Ohne Antwort bleibt es gezählt und geht mit der nächsten Meldung hinaus
    } finally {
      this.#sendet = false;
    }
  }

  /** Läuft im Sekundentakt; liefert das Aufräumen, das noch meldet, was offen ist */
  starte(): () => void {
    const uhr = setInterval(() => this.schritt(), 1000);
    const weg = () => void this.melde(true);
    const verdeckt = () => document.visibilityState === "hidden" && weg();
    addEventListener("pagehide", weg);
    document.addEventListener("visibilitychange", verdeckt);
    return () => {
      clearInterval(uhr);
      removeEventListener("pagehide", weg);
      document.removeEventListener("visibilitychange", verdeckt);
      weg();
    };
  }
}
