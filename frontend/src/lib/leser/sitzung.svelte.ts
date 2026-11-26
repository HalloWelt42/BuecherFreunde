// Eine Lesesitzung: Markierungen, Notizen und Etiketten des Buchs, offenes Feld, Auswahl, Stift. Der Leser jedes Formats
// hängt seine Griffe ein (springen, zeigen), die Felder rufen nur diese Sitzung.
import { aktualisiereHighlight, erstelleHighlight, highlightsFuerBuch, loescheHighlight } from "../api/highlights";
import { aktualisiereLabel, erstelleLabel, labelsFuerBuch, loescheLabel } from "../api/labels";
import { aktualisiereNotiz, erstelleNotiz, loescheNotiz, notizenFuerBuch } from "../api/notes";
import { randeintraege } from "./randmarken";
import { ordne } from "./stellensprung";
import { bestand } from "../stand/bestand.svelte";
import { melde } from "../stand/meldungen.svelte";
import { notizblock } from "../stand/notizblock.svelte";
import { frage } from "../stand/rueckfrage.svelte";
import { schale } from "../stand/schale.svelte";
import { vorlesen } from "../stand/vorlesen.svelte";
import type { BuchEinzeln, Etikett, Markierung, Notiz } from "../typen";
import type { Buchquelle } from "../vorlesen/typen";
import type { Codestelle } from "../api/ausfuehren";
import type { Codelage } from "./text/codeorte";
import type { Randeintrag } from "./randmarken";
import type { Kasten } from "./fokus";
import type { Leseart } from "./fluss/fluss";
import { VORGABE_STIFT } from "./farben";
import { originalfassung, type Lesefassung } from "./lesefassung";
import type { Feldname, Kapitel, Textauswahl } from "./typen";
import { Verzoegert } from "./verzoegert";

const SPIELER_MS = 3500;

/** Wo die Marken am Rand stehen: der Leser des Formats weiß es */
export interface Randort {
  /** Anteil im Buch, 0 bis 1 */
  anteil(e: Randeintrag): number | null;
  /** Höhe der Stelle im Fenster, wenn sie auf der offenen Seite zu sehen ist */
  lage(e: Randeintrag): number | null;
  /** Rechte Kante des Blatts im Fenster */
  kante(): number | null;
  /** Anteil der offenen Stelle, in derselben Rechnung wie `anteil` (für vorige und nächste Stelle, BF-63) */
  stand(): number;
}

/** Wo die Codestellen eines Texts stehen (Markdown, Text, EPUB; BF-29): der Leser des Formats weiß es */
export interface Codeort {
  /** Die Codeblöcke auf dem Schirm, je mit der Stelle, dem wievielten Teil, der Lage im Fenster und den Zeilen knapp darüber */
  orte(): Codelage[];
  /** Ein Listing ins Fenster Ausführen */
  oeffne(stelle: Codestelle): void;
}

/** Was die Lesehilfen vom Leser des Formats brauchen */
export interface Hilfeort {
  /** Das Blatt im Fenster */
  blatt(): DOMRect | null;
  zeilenhoehe(): number;
  /** Absatz unter einem Punkt im Fenster; null, wo es keine Absätze gibt (PDF als Bild) */
  absatzBei(x: number, y: number): Kasten | null;
  /** Absatz und Zeile, in denen gerade vorgelesen wird */
  vorgelesen(): { absatz: Kasten | null; zeile: Kasten | null };
  readonly mitAbsaetzen: boolean;
  /** Ein Stück weiter, von selbst; false am Ende */
  rolle(px: number): boolean;
  blaettere(): boolean;
  art(): Leseart;
}

export interface Lesegriffe {
  zumKapitel(k: Kapitel): void;
  zurMarkierung(m: Markierung): void;
  /** An eine Notiz oder ein Etikett; false, wenn keine Stelle bekannt ist */
  zurStelle(ort: string, cfi: string, prozent: number): boolean;
  /** Markierungen im Buch neu zeichnen */
  zeichne(): void;
  /** Wo man gerade liest, für neue Notizen und Etiketten */
  hier(): { ort: string; prozent: number; cfi: string };
}

export class Lesesitzung {
  markierungen = $state<Markierung[]>([]);
  notizen = $state<Notiz[]>([]);
  etiketten = $state<Etikett[]>([]);
  /** Alle Stellen mit Notiz, Markierung oder Etikett, deren Anteil der Leser kennt, nach dem Anteil (BF-63) */
  stellen = $derived.by(() => {
    const rand = this.rand;
    return rand ? ordne(randeintraege(this.markierungen, this.notizen, this.etiketten), (e) => rand.anteil(e)) : [];
  });
  feld = $state<Feldname>("");
  /** Ein neues Etikett soll entstehen (Kontextmenü "Etikett hier"): das Feld Notizen öffnet seine Eingabe */
  etikettWunsch = $state(false);
  kapitel = $state<Kapitel[]>([]);
  kapitelJetzt = $state(-1);
  auswahl = $state<Textauswahl | null>(null);
  stift = $state(false);
  stiftfarbe = $state(VORGABE_STIFT);
  griffe: Lesegriffe | null = null;
  spieler = $state(false);
  /** Ruhe: Leisten und Zeiger sind ausgeblendet, bis sich etwas regt */
  ruhig = $state(false);
  #spielerUhr: ReturnType<typeof setTimeout> | undefined;
  /** Woraus vorgelesen wird; der Leser des Formats setzt sie, sobald das Buch steht */
  quelle = $state.raw<Buchquelle | null>(null);
  rand = $state.raw<Randort | null>(null);
  /** Schlüssel des Eintrags, dessen Karte am Rand aufgeklappt ist (Randmarken, nach einem Sprung von unten, BF-63) */
  randOffen = $state("");
  /** Zuletzt angesprungene Stelle: von ihr geht es weiter, solange man dort steht */
  gesprungen = $state("");
  /** Codestellen mit Taste in Texten; null ohne Sandbox oder im PDF (dort hängen sie an der Seite) */
  code = $state.raw<Codeort | null>(null);
  hilfe = $state.raw<Hilfeort | null>(null);
  /** Farben des Blatts, für Voreinstellungen */
  farbwahl = $state.raw<{ jetzt(): { fg: string; bg: string }; setze(fg: string, bg: string): void } | null>(null);
  /** Wo der Zeiger über dem Buch steht, im Fenster */
  zeiger = $state<{ x: number; y: number } | null>(null);
  /** Tasten, die vor denen des Lesers gelten (Lineal, Kürzel); true, wenn erledigt */
  vortaste: ((e: KeyboardEvent) => boolean) | null = null;
  /** Zählt jede Bewegung der Ansicht, damit, was am Text hängt, mitgeht */
  bewegung = $state(0);
  /** Trifft ein Tippen eine Marke am Rand? Dann gehört es ihr. */
  randtreffer: ((x: number, y: number) => boolean) | null = null;
  #spaeter = new Verzoegert();

  /** Was gelesen wird: das Original oder eine Übersetzung (BF-71); an einer Übersetzung hängen keine Stellen */
  readonly fassung: Lesefassung;

  constructor(public buch: BuchEinzeln, fassung?: Lesefassung) {
    this.fassung = fassung ?? originalfassung(buch);
  }

  /** Notizen, Markierungen und Etiketten gehören zum Original */
  get mitStellen(): boolean {
    return this.fassung.mitStellen;
  }

  async laden(): Promise<void> {
    if (!this.mitStellen) return;
    const [m, n, e] = await Promise.allSettled([highlightsFuerBuch(this.buch.id), notizenFuerBuch(this.buch.id), labelsFuerBuch(this.buch.id)]);
    if (m.status === "fulfilled") this.markierungen = m.value;
    if (n.status === "fulfilled") this.notizen = n.value;
    if (e.status === "fulfilled") this.etiketten = e.value;
    this.griffe?.zeichne();
  }

  /** Etiketten gibt es in Text und Markdown; wo schon welche hängen, auch dort */
  get mitEtiketten(): boolean {
    return this.mitStellen && (["md", "txt"].includes(this.buch.file_format) || this.etiketten.length > 0);
  }

  /** Etikett an der Stelle, an der man liest: das Feld Notizen mit offener Eingabe */
  etikettHier(): void {
    this.feld = "stellen";
    this.etikettWunsch = true;
  }

  schalteFeld(feld: Feldname): void {
    this.feld = this.feld === feld ? "" : feld;
  }

  /** Tippen in die Mitte: Leisten aus und wieder ein, ohne das Vollbild des Browsers. Liest es im Vollbild vor, kommt erst der Spieler. */
  tippeMitte(): void {
    if (schale.vollbild && vorlesen.aktiv && !this.spieler) return this.zeigeSpieler();
    schale.vollbild = !schale.vollbild;
  }

  /** Die Maus bewegt sich über dem Buch: im Vollbild kommt, wenn vorgelesen wird, der Spieler */
  regt(e: PointerEvent): void {
    if (e.pointerType === "mouse" && schale.vollbild && vorlesen.aktiv && vorlesen.quelle === this.quelle) this.zeigeSpieler();
  }

  /** Der schmale Spieler im Vollbild, für ein paar Sekunden; bleibt, solange man auf ihm ist */
  zeigeSpieler(bleibt = false): void {
    this.spieler = true;
    clearTimeout(this.#spielerUhr);
    if (!bleibt) this.#spielerUhr = setTimeout(() => (this.spieler = false), SPIELER_MS);
  }

  /** Die Ansicht hat sich bewegt */
  bewegt(): void {
    this.bewegung++;
    vorlesen.bewegt();
  }

  /** Ein Tippen schließt erst das offene Feld; eine Auswahl im Text und die Marken am Rand gehen ebenso vor */
  belegt(punkt?: { x: number; y: number }): boolean {
    if (punkt && this.randtreffer?.(punkt.x, punkt.y)) return true;
    if (!this.feld) return this.auswahl !== null;
    this.feld = "";
    return true;
  }

  /** Ausstehende Änderungen sofort schicken */
  beende(): void {
    this.#spaeter.alle();
  }

  async #versuche(tun: () => Promise<void>, vorab = "Nicht gespeichert"): Promise<boolean> {
    try {
      await tun();
      return true;
    } catch (e) {
      melde.schlecht(e, vorab);
      return false;
    }
  }

  // Markierungen

  async markiere(a: Textauswahl, farbe: string): Promise<void> {
    if (!this.mitStellen) return;
    this.stiftfarbe = farbe;
    await this.#versuche(async () => {
      const neu = await erstelleHighlight(this.buch.id, { cfi_range: a.cfi, color: farbe, text_snippet: a.text.slice(0, 500) });
      this.markierungen = [...this.markierungen, neu];
      this.griffe?.zeichne();
      void bestand.laden();
    });
  }

  aendereMarkierung(id: number, daten: Partial<Pick<Markierung, "color" | "label_name" | "label_note">>): void {
    this.markierungen = this.markierungen.map((m) => (m.id === id ? { ...m, ...daten } : m));
    if (daten.color) this.griffe?.zeichne();
    const tun = () => this.#versuche(async () => void (await aktualisiereHighlight(id, daten)));
    if (daten.color) void tun();
    else this.#spaeter.rufe(`markierung-${id}-${Object.keys(daten)[0]}`, tun);
  }

  async loescheMarkierung(m: Markierung): Promise<void> {
    const folgen = [`Die Stelle "${(m.text_snippet || "Markierung").slice(0, 80)}" ist danach nicht mehr markiert.`];
    if (m.label_name || m.label_note) folgen.push("Name und Notiz der Markierung gehen verloren.");
    if (!(await frage({ titel: "Markierung löschen?", folgen, ja: "Löschen" }))) return;
    await this.#versuche(async () => {
      await loescheHighlight(m.id);
      this.markierungen = this.markierungen.filter((x) => x.id !== m.id);
      this.griffe?.zeichne();
      void bestand.laden();
    }, "Nicht gelöscht");
  }

  // Buchnotizen

  async neueNotiz(text: string, ort?: string): Promise<boolean> {
    if (!this.mitStellen) return false;
    return this.#versuche(async () => {
      const neu = await erstelleNotiz(this.buch.id, { content: text, page_reference: ort ?? this.griffe?.hier().ort ?? "" });
      this.notizen = [neu, ...this.notizen];
    });
  }

  aendereNotiz(id: number, text: string): void {
    this.notizen = this.notizen.map((n) => (n.id === id ? { ...n, content: text } : n));
    this.#spaeter.rufe(`notiz-${id}`, () => this.#versuche(async () => void (await aktualisiereNotiz(id, { content: text }))));
  }

  /** Auswahl an eine Notiz hängen oder sie damit ersetzen */
  async setzeNotiz(n: Notiz, text: string): Promise<void> {
    await this.#versuche(async () => {
      await aktualisiereNotiz(n.id, { content: text });
      this.notizen = this.notizen.map((x) => (x.id === n.id ? { ...x, content: text } : x));
    });
  }

  async loescheNotiz(n: Notiz): Promise<void> {
    if (!(await frage({ titel: "Notiz löschen?", folgen: [`Der Text "${n.content.slice(0, 80)}" geht verloren.`], ja: "Löschen" }))) return;
    await this.#versuche(async () => {
      await loescheNotiz(n.id);
      this.notizen = this.notizen.filter((x) => x.id !== n.id);
    }, "Nicht gelöscht");
  }

  // Etiketten (Textbücher)

  async neuesEtikett(name: string, note: string, farbe: string): Promise<boolean> {
    if (!this.mitStellen) return false;
    const hier = this.griffe?.hier() ?? { ort: "", prozent: 0, cfi: "" };
    return this.#versuche(async () => {
      const neu = await erstelleLabel(this.buch.id, { color: farbe, name: name.slice(0, 50), note, page_reference: hier.ort, position_percent: hier.prozent, cfi_reference: hier.cfi });
      this.etiketten = [...this.etiketten, neu];
    });
  }

  aendereEtikett(id: number, daten: Partial<Pick<Etikett, "name" | "note" | "color">>): void {
    this.etiketten = this.etiketten.map((e) => (e.id === id ? { ...e, ...daten } : e));
    this.#spaeter.rufe(`etikett-${id}-${Object.keys(daten)[0]}`, () => this.#versuche(async () => void (await aktualisiereLabel(id, daten))));
  }

  async loescheEtikett(e: Etikett): Promise<void> {
    if (!(await frage({ titel: "Etikett löschen?", folgen: [`Das Etikett "${e.name || "ohne Namen"}" geht verloren${e.note ? ", mit seiner Notiz" : ""}.`], ja: "Löschen" }))) return;
    await this.#versuche(async () => {
      await loescheLabel(e.id);
      this.etiketten = this.etiketten.filter((x) => x.id !== e.id);
    }, "Nicht gelöscht");
  }

  // Schnellnotiz

  anSchnellnotiz(text: string): void {
    notizblock.haengeAn(text);
    melde.gut("An die Schnellnotiz angehängt");
  }

  async ersetzeSchnellnotiz(text: string): Promise<void> {
    if (notizblock.text.trim()) {
      const ja = await frage({ titel: "Schnellnotiz ersetzen?", folgen: [`Der bisherige Text mit ${notizblock.woerter} Wörtern geht verloren.`], ja: "Ersetzen", symbol: "right-left" });
      if (!ja) return;
    }
    notizblock.text = text;
    melde.gut("Schnellnotiz ersetzt");
  }
}

/** Auswahl mit ihrer Stelle, für Notizen */
export function alsZitat(a: Textauswahl): string {
  return a.ort ? `[${a.ort}] "${a.text}"` : `"${a.text}"`;
}
