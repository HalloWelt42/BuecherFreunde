// Eine Lesesitzung: Markierungen, Notizen und Etiketten des Buchs, offenes Feld, Auswahl, Stift. Der Leser jedes Formats
// hängt seine Griffe ein (springen, zeigen), die Felder rufen nur diese Sitzung.
import { aktualisiereHighlight, erstelleHighlight, highlightsFuerBuch, loescheHighlight } from "../api/highlights";
import { aktualisiereLabel, erstelleLabel, labelsFuerBuch, loescheLabel } from "../api/labels";
import { aktualisiereNotiz, erstelleNotiz, loescheNotiz, notizenFuerBuch } from "../api/notes";
import { bestand } from "../stand/bestand.svelte";
import { melde } from "../stand/meldungen.svelte";
import { notizblock } from "../stand/notizblock.svelte";
import { frage } from "../stand/rueckfrage.svelte";
import type { BuchEinzeln, Etikett, Markierung, Notiz } from "../typen";
import { VORGABE_STIFT } from "./farben";
import type { Feldname, Kapitel, Textauswahl } from "./typen";
import { Verzoegert } from "./verzoegert";

export interface Lesegriffe {
  zumKapitel(k: Kapitel): void;
  zurMarkierung(m: Markierung): void;
  /** An eine Notiz oder ein Etikett; false, wenn keine Stelle bekannt ist */
  zurStelle(ort: string, cfi: string, prozent: number): boolean;
  /** Markierungen im Buch neu zeichnen */
  zeichne(): void;
  /** Wo man gerade liest, für neue Notizen und Etiketten */
  hier(): { ort: string; prozent: number; cfi: string };
  /** Text der Seite oder des Kapitels, zum Vorlesen */
  abschnitt(): Promise<string>;
  abschnittName: string;
}

export class Lesesitzung {
  markierungen = $state<Markierung[]>([]);
  notizen = $state<Notiz[]>([]);
  etiketten = $state<Etikett[]>([]);
  feld = $state<Feldname>("");
  kapitel = $state<Kapitel[]>([]);
  kapitelJetzt = $state(-1);
  auswahl = $state<Textauswahl | null>(null);
  stift = $state(false);
  stiftfarbe = $state(VORGABE_STIFT);
  griffe: Lesegriffe | null = null;
  #spaeter = new Verzoegert();

  constructor(public buch: BuchEinzeln) {}

  async laden(): Promise<void> {
    const [m, n, e] = await Promise.allSettled([highlightsFuerBuch(this.buch.id), notizenFuerBuch(this.buch.id), labelsFuerBuch(this.buch.id)]);
    if (m.status === "fulfilled") this.markierungen = m.value;
    if (n.status === "fulfilled") this.notizen = n.value;
    if (e.status === "fulfilled") this.etiketten = e.value;
    this.griffe?.zeichne();
  }

  schalteFeld(feld: Feldname): void {
    this.feld = this.feld === feld ? "" : feld;
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
