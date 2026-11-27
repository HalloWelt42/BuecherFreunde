// Das Formular "Bearbeiten" (BF-112): die Eingaben, was die Werkzeuge eingesetzt haben (Felder, Umschlag, Regale) und das
// Speichern in einem Zug. Übernommenes kommt ins Formular, ins Buch erst mit Speichern (Abnahme BF-111, Frage 1); Abbrechen
// verwirft alles.
import { uebernehmVorschlaege } from "../../lib/api/ai";
import { aktualisiereBuch, umschlagAusDatei, umschlagNeu } from "../../lib/api/books";
import { buchAusSammlung, buchZuordnen } from "../../lib/api/collections";
import { uebernehmMetadaten, type Aktuell } from "../../lib/api/metadata";
import { anzahl } from "../../lib/format";
import { quellen } from "../../lib/stand/quellen.svelte";
import type { BuchEinzeln } from "../../lib/typen";
import { ALLE, DATEI, LEXIKON, nutzlast } from "./angaben";
import type { Angabenziel, Auswahl } from "./ziel";

/** Felder des Formulars, die ein Werkzeug setzen kann */
export type Textfeld = "title" | "author" | "isbn" | "year" | "publisher" | "language" | "page_count" | "description";
/** Feld des Vergleichs (angaben.ts) -> Feld des Formulars */
const FELD: Record<string, Textfeld> = { titel: "title", autor: "author", verlag: "publisher", jahr: "year", seiten: "page_count", isbn: "isbn", sprache: "language", beschreibung: "description" };
const GESPEICHERT_MIT = "Gespeichert wird mit Speichern.";

export interface NeuerUmschlag {
  adresse: string;
  /** aus der Datei (gespeichert über neu-extrahieren) oder von einer Quelle (über die Übernahme) */
  ausDatei: boolean;
  quelle: string;
}

const text = (w: unknown) => (w === null || w === undefined ? "" : String(w));

function woher(quelle: string): string {
  if (quelle === ALLE) return "den Verzeichnissen";
  if (quelle === DATEI) return "der Datei";
  if (quelle === LEXIKON) return "dem Lexikon";
  return quellen.namen[quelle] ?? "der Quelle";
}

const regalwort = (namen: string[]) => `${namen.length === 1 ? "das Regal" : "die Regale"} ${namen.join(", ")}`;

function alsZahl(wert: string, feld: string): number | null {
  if (!wert.trim()) return null;
  if (!/^\d{1,5}$/.test(wert.trim())) throw new Error(`${feld} ist keine Zahl`);
  return Number(wert.trim());
}

export class Buchformular implements Angabenziel {
  readonly sofort = false;
  eingabe = $state({ title: "", author: "", isbn: "", year: "", publisher: "", language: "", page_count: "", typ: "", gattung: "", sammlung: "", band: "", description: "" });
  /** Felder, die ein Werkzeug gesetzt hat; sie stehen messingfarben hinterlegt */
  eingesetzt = $state<Textfeld[]>([]);
  umschlag = $state<NeuerUmschlag | null>(null);
  /** Regale aus dem Vergleich und aus dem Vorschlag der KI, gespeichert mit Speichern */
  regaleAngaben = $state<string[]>([]);
  regaleKi = $state<string[]>([]);
  /** Was zuletzt eingesetzt wurde, in einem Satz */
  hinweis = $state("");
  readonly #buch: BuchEinzeln;

  constructor(buch: BuchEinzeln) {
    this.#buch = buch;
    this.eingabe = {
      title: buch.title, author: buch.author, isbn: buch.isbn, year: buch.year ? String(buch.year) : "", publisher: buch.publisher, language: buch.language,
      page_count: buch.page_count ? String(buch.page_count) : "", typ: buch.typ, gattung: buch.gattung ?? "", sammlung: buch.sammlung_id ? String(buch.sammlung_id) : "",
      band: buch.band_nummer, description: buch.description,
    };
  }

  #setze(feld: Textfeld, wert: string): void {
    this.eingabe[feld] = wert;
    if (!this.eingesetzt.includes(feld)) this.eingesetzt = [...this.eingesetzt, feld];
  }

  // -- Angabenziel ---------------------------------------------------------------------------------------------------
  aktuell(): Aktuell {
    const e = this.eingabe;
    return { titel: e.title, autor: e.author, verlag: e.publisher, jahr: e.year, seiten: e.page_count, isbn: e.isbn, sprache: e.language, beschreibung: e.description,
      hat_cover: !!this.#buch.cover_path || !!this.umschlag, kategorien: [...this.#buch.categories.map((c) => c.name), ...this.regaleAngaben, ...this.regaleKi] };
  }

  frage(): { titel: string; autor: string } {
    return { titel: this.eingabe.title, autor: this.eingabe.author };
  }

  bild(): string | null {
    return this.umschlag?.adresse ?? null;
  }

  async angaben(a: Auswahl): Promise<void> {
    const daten = nutzlast(a.vorschlag, a.quelle, a.gewaehlt, a.listen);
    let felder = 0;
    for (const [schluessel, feld] of Object.entries(FELD)) {
      if (!(schluessel in daten)) continue;
      this.#setze(feld, text(daten[schluessel]));
      felder += 1;
    }
    if (typeof daten.cover_url === "string") {
      this.#neuerUmschlag({ adresse: daten.cover_url, ausDatei: false, quelle: a.quelle });
      felder += 1;
    }
    const regale = ((daten.kategorien as string[] | undefined) ?? []).filter((r) => !this.regaleAngaben.includes(r));
    this.regaleAngaben = [...this.regaleAngaben, ...regale];
    const von = woher(a.quelle);
    this.hinweis = felder
      ? `${anzahl(felder, "Feld", "Felder")} aus ${von} eingesetzt${regale.length ? `, dazu ${regalwort(regale)}` : ""}. ${GESPEICHERT_MIT}`
      : `Aus ${von} kommt ${regalwort(regale)} dazu. ${GESPEICHERT_MIT}`;
  }

  async isbn(isbn: string): Promise<void> {
    this.#setze("isbn", isbn);
    this.hinweis = `ISBN aus dem Buch eingesetzt. ${GESPEICHERT_MIT}`;
  }

  async beschreibung(wert: string): Promise<void> {
    this.#setze("description", wert);
    this.hinweis = `Beschreibung aus dem Buchtext eingesetzt. ${GESPEICHERT_MIT}`;
  }

  async regale(namen: string[]): Promise<void> {
    const neu = namen.filter((n) => !this.regaleKi.includes(n));
    this.regaleKi = [...this.regaleKi, ...neu];
    this.hinweis = `Die KI schlägt ${regalwort(namen)} vor. ${GESPEICHERT_MIT}`;
  }

  async umschlagAusDatei(): Promise<void> {
    const bild = await umschlagAusDatei(this.#buch.id);
    this.#neuerUmschlag({ adresse: URL.createObjectURL(bild), ausDatei: true, quelle: "" });
    this.hinweis = `Umschlag aus der Datei eingesetzt. ${GESPEICHERT_MIT}`;
  }

  #neuerUmschlag(u: NeuerUmschlag): void {
    this.#freigeben();
    this.umschlag = u;
  }

  #freigeben(): void {
    if (this.umschlag?.ausDatei) URL.revokeObjectURL(this.umschlag.adresse);
  }

  // -- Speichern -----------------------------------------------------------------------------------------------------
  /** Was sich an den Feldern geändert hat; wirft mit einem Satz, wenn etwas nicht stimmt */
  aenderungen(): Record<string, unknown> {
    const e = this.eingabe;
    const daten: Record<string, unknown> = {};
    for (const k of ["title", "author", "isbn", "publisher", "language", "typ", "gattung", "description"] as const) {
      if (e[k] !== (this.#buch[k] ?? "")) daten[k] = e[k];
    }
    if (!e.title.trim()) throw new Error("Der Titel fehlt");
    if ("author" in daten && !e.author.trim()) throw new Error("Der Autor fehlt");
    const jahr = alsZahl(e.year, "Das Jahr");
    if (jahr !== this.#buch.year) daten.year = jahr;
    const seiten = alsZahl(e.page_count, "Die Seitenzahl") ?? 0;
    if (seiten !== this.#buch.page_count) daten.page_count = seiten;
    return daten;
  }

  async #sammlung(): Promise<void> {
    const neu = this.eingabe.sammlung ? Number(this.eingabe.sammlung) : null;
    if (neu === this.#buch.sammlung_id && this.eingabe.band === this.#buch.band_nummer) return;
    if (neu) await buchZuordnen(neu, this.#buch.id, this.eingabe.band);
    else if (this.#buch.sammlung_id) await buchAusSammlung(this.#buch.sammlung_id, this.#buch.id);
  }

  /** Alles auf einmal: Felder, Sammlung, Umschlag, Regale. Gibt zurück, was nicht ging (Umschlag), sonst leer. */
  async speichern(): Promise<string> {
    const daten = this.aenderungen();
    await this.#sammlung();
    if (Object.keys(daten).length) await aktualisiereBuch(this.#buch.id, daten);
    if (this.umschlag?.ausDatei) await umschlagNeu(this.#buch.id);
    const vonQuelle = this.umschlag && !this.umschlag.ausDatei ? { cover_url: this.umschlag.adresse, quelle: this.umschlag.quelle } : {};
    let fehlt = "";
    if ("cover_url" in vonQuelle || this.regaleAngaben.length) {
      const e = await uebernehmMetadaten(this.#buch.id, { ...vonQuelle, ...(this.regaleAngaben.length ? { kategorien: this.regaleAngaben } : {}) });
      fehlt = e.hinweis;
    }
    if (this.regaleKi.length) await uebernehmVorschlaege(this.#buch.id, this.regaleKi);
    this.#freigeben();
    return fehlt;
  }

  /** Abbrechen oder fort: ein Bild aus der Datei gibt seinen Speicher frei */
  verwerfen(): void {
    this.#freigeben();
  }
}
