// Katalog pflegen (BF-69): wählen (Standard, an den Bestand angepasst, leer, aus einer Datei), den Entwurf annehmen oder
// verwerfen, Bereiche und Kategorien ändern. Ändern geht an den Entwurf, solange es einen gibt, sonst an den gültigen
// Katalog; beides steht hinter derselben Schnittstelle (Katalogquelle). Der Lauf "an den Bestand anpassen" steht unter
// Aufträge und geht weiter, wenn man die Einstellungen verlässt.
import {
  aendereBereich, aendereKategorie, beginneEntwurf, katalogDatei, ladeEntwurf, ladeKatalogDatei, ladeStandard, legeBereichAn, legeKategorieAn,
  loesche, loeschfolgen, nimmEntwurfAn, speichereEntwurf, verwirfEntwurf, type Bereichsangaben,
} from "../../../lib/api/katalog";
import { anzahl } from "../../../lib/format";
import { regelnAus, umfang } from "../../../lib/katalog";
import { auftraege } from "../../../lib/stand/auftraege.svelte";
import { bestand } from "../../../lib/stand/bestand.svelte";
import { melde } from "../../../lib/stand/meldungen.svelte";
import { frage } from "../../../lib/stand/rueckfrage.svelte";
import type { Katalogbereich, Katalogentwurf, Katalogkategorie, Katalogweg, Kategorieregeln, Laufstand } from "../../../lib/typen";
import { entferneBereich, entferneKategorie, neuerBereichsschluessel, neuerKategorieschluessel, setzeBereich, setzeKategorie } from "./entwurf";

const TAKT_MS = 1500;
const AUFTRAG = "katalog-entwurf";
const TITEL = "Katalog an den Bestand anpassen";
const WEG = "/settings/katalog";

/** Was das Fenster an einer Kategorie ändert; der Bereich wird eigens gewählt */
export interface Kategoriefelder {
  name: string;
  zeichen: string;
  farbe: string;
  ki_beschreibung: string;
  regeln: Kategorieregeln;
  verborgen: boolean;
}

/** Eine Kategorie an ihrer Stelle im Katalog */
export interface Kategoriestelle {
  kategorie: Katalogkategorie;
  bereich: Katalogbereich;
}

/** Wohin Änderungen gehen: an den Entwurf oder an den gültigen Katalog */
interface Katalogquelle {
  speichereBereich(alt: Katalogbereich | null, angaben: Bereichsangaben): Promise<void>;
  speichereKategorie(alt: Kategoriestelle | null, ziel: Katalogbereich, felder: Kategoriefelder): Promise<void>;
  /** Folgen fürs Entfernen; null: geht nicht, der Grund ist gemeldet */
  bereichsfolgen(b: Katalogbereich): Promise<string[] | null>;
  kategoriefolgen(stelle: Kategoriestelle): Promise<string[]>;
  entferneBereich(b: Katalogbereich): Promise<void>;
  entferneKategorie(stelle: Kategoriestelle): Promise<void>;
}

/** Die ersten betroffenen Bücher mit Namen, der Rest als Zahl */
export function betroffene(titel: readonly string[], gesamt: number): string[] {
  if (!titel.length) return [];
  const rest = gesamt - titel.length;
  return [`Betroffen: ${titel.join(", ")}${rest > 0 ? ` und ${anzahl(rest, "weiteres", "weitere")}` : ""}.`];
}

/** Die Farbe des Bereichs gilt, solange die Kategorie keine andere hat */
const eigeneFarbe = (felder: Kategoriefelder, ziel: Katalogbereich) => (felder.farbe.toLowerCase() === ziel.farbe.toLowerCase() ? "" : felder.farbe);

const gueltig: Katalogquelle = {
  async speichereBereich(alt, angaben) {
    if (alt?.id !== undefined) await aendereBereich(alt.id, angaben);
    else await legeBereichAn(angaben);
    bestand.geaendert();
  },
  async speichereKategorie(alt, ziel, felder) {
    const angaben = { ...felder, bereich_id: ziel.id!, farbe: eigeneFarbe(felder, ziel), regeln: regelnAus(felder.regeln) };
    if (alt?.kategorie.id !== undefined) await aendereKategorie(alt.kategorie.id, angaben);
    else await legeKategorieAn(angaben);
    bestand.geaendert();
  },
  async bereichsfolgen(b) {
    const f = await loeschfolgen("bereiche", b.id!);
    if (f.kategorien) {
      melde.warn(`Erst die ${anzahl(f.kategorien, "Kategorie", "Kategorien")} in ${b.name} verschieben oder entfernen`);
      return null;
    }
    return ["Name, Zeichen, Farbe und Beschreibung des Bereichs gehen verloren."];
  },
  async kategoriefolgen({ kategorie }) {
    const f = await loeschfolgen("kategorien", kategorie.id!);
    return [
      f.buecher ? `${anzahl(f.buecher, "Buch verliert", "Bücher verlieren")} diese Kategorie, die Bücher selbst bleiben.` : "Kein Buch steht in dieser Kategorie.",
      ...betroffene(f.titel, f.buecher),
      ...(f.vorschlaege ? [`${anzahl(f.vorschlaege, "offener Vorschlag entfällt", "offene Vorschläge entfallen")}.`] : []),
      "Name, Zeichen, Beschreibung und Regeln gehen verloren.",
    ];
  },
  async entferneBereich(b) {
    await loesche("bereiche", b.id!);
    bestand.geaendert();
  },
  async entferneKategorie({ kategorie }) {
    await loesche("kategorien", kategorie.id!);
    bestand.geaendert();
  },
};

class Katalogpflege {
  entwurf = $state<Katalogentwurf | null>(null);
  /** Lauf "an den Bestand anpassen" */
  lauf = $state<Laufstand | null>(null);
  /** Umfang des Standard-Katalogs für seine Kachel */
  standard = $state<{ bereiche: number; kategorien: number } | null>(null);
  geladen = $state(false);
  fehler = $state("");
  /** Ein Weg wird gerade begonnen */
  beginnt = $state<Katalogweg | "">("");
  #verfolgt = false;

  /** Was die Kacheln zeigen: der Entwurf, sonst der gültige Katalog */
  bereiche = $derived(this.entwurf?.bereiche ?? (bestand.katalog?.hat_katalog ? bestand.katalog.bereiche : []));
  hatKatalog = $derived(!!bestand.katalog?.hat_katalog);
  passtAn = $derived(!!this.lauf && (this.lauf.laeuft || this.lauf.pause));

  /** Änderungen gehen an den Entwurf, solange es einen gibt */
  get #quelle(): Katalogquelle {
    return this.entwurf ? this.#entwurfsquelle : gueltig;
  }

  async laden(): Promise<void> {
    try {
      const stand = await ladeEntwurf();
      this.entwurf = stand.entwurf;
      this.lauf = stand.lauf;
      this.fehler = "";
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
    } finally {
      this.geladen = true;
    }
    if (!this.standard) {
      try {
        this.standard = umfang((await ladeStandard()).bereiche);
      } catch {
        // ohne Zahlen steht die Kachel trotzdem da
      }
    }
    if (this.passtAn) void this.#verfolge();
  }

  async waehle(weg: Katalogweg): Promise<void> {
    if (this.passtAn || this.beginnt) return;
    if (this.entwurf && !(await this.#ersetzeEntwurf())) return;
    this.beginnt = weg;
    try {
      const antwort = await beginneEntwurf(weg);
      if (weg === "bestand") {
        this.lauf = antwort.lauf ?? null;
        void this.#verfolge();
      } else {
        this.entwurf = antwort.entwurf ?? (await ladeEntwurf()).entwurf;
      }
    } catch (e) {
      melde.schlecht(e, "Nicht begonnen");
    } finally {
      this.beginnt = "";
    }
  }

  async annehmen(): Promise<void> {
    try {
      bestand.katalog = await nimmEntwurfAn();
      this.entwurf = null;
      melde.gut("Katalog angenommen");
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht angenommen");
    }
  }

  async verwerfen(): Promise<void> {
    const ja = await frage({
      titel: "Vorschlag verwerfen?",
      folgen: [this.#entwurfsumfang(), "Änderungen daran gehen verloren.", ...(this.hatKatalog ? ["Der gültige Katalog bleibt, wie er ist."] : [])],
      ja: "Verwerfen",
    });
    if (!ja) return;
    try {
      await verwirfEntwurf();
      this.entwurf = null;
      melde.info("Vorschlag verworfen");
    } catch (e) {
      melde.schlecht(e, "Nicht verworfen");
    }
  }

  /** Eine Katalog-Datei laden: sie wird zum Entwurf */
  async ladeDatei(datei: File): Promise<void> {
    let inhalt: unknown;
    try {
      inhalt = JSON.parse(await datei.text());
    } catch {
      melde.schlecht(`${datei.name} ist keine Katalog-Datei`);
      return;
    }
    if (this.entwurf && !(await this.#ersetzeEntwurf())) return;
    try {
      this.entwurf = (await ladeKatalogDatei(inhalt)).entwurf;
      melde.gut("Katalog geladen, als Vorschlag");
    } catch (e) {
      melde.schlecht(e, "Nicht geladen");
    }
  }

  /** Den gültigen Katalog als Datei sichern */
  async sichere(): Promise<void> {
    try {
      const adresse = URL.createObjectURL(await katalogDatei());
      const verweis = Object.assign(document.createElement("a"), { href: adresse, download: "katalog.json" });
      verweis.click();
      setTimeout(() => URL.revokeObjectURL(adresse), 10_000);
    } catch (e) {
      melde.schlecht(e, "Nicht gesichert");
    }
  }

  // Ändern, über die Quelle

  async speichereBereich(alt: Katalogbereich | null, angaben: Bereichsangaben): Promise<boolean> {
    return this.#tue(() => this.#quelle.speichereBereich(alt, angaben), alt ? "Bereich geändert" : "Bereich angelegt");
  }

  async speichereKategorie(alt: Kategoriestelle | null, ziel: Katalogbereich, felder: Kategoriefelder): Promise<boolean> {
    return this.#tue(() => this.#quelle.speichereKategorie(alt, ziel, felder), alt ? "Kategorie geändert" : "Kategorie angelegt");
  }

  /** Eine Kategorie in einen anderen Bereich ziehen */
  async verschiebe(stelle: Kategoriestelle, ziel: Katalogbereich): Promise<void> {
    if (stelle.bereich.schluessel === ziel.schluessel) return;
    const { name, zeichen, farbe, ki_beschreibung, regeln, verborgen } = stelle.kategorie;
    await this.#tue(() => this.#quelle.speichereKategorie(stelle, ziel, { name, zeichen, farbe, ki_beschreibung, regeln, verborgen }), `${name} steht jetzt in ${ziel.name}`);
  }

  async entferneBereich(b: Katalogbereich): Promise<boolean> {
    try {
      const folgen = await this.#quelle.bereichsfolgen(b);
      if (!folgen || !(await frage({ titel: `Bereich ${b.name} entfernen?`, folgen, ja: "Bereich entfernen" }))) return false;
    } catch (e) {
      melde.schlecht(e);
      return false;
    }
    return this.#tue(() => this.#quelle.entferneBereich(b), "Bereich entfernt");
  }

  async entferneKategorie(stelle: Kategoriestelle): Promise<boolean> {
    try {
      const folgen = await this.#quelle.kategoriefolgen(stelle);
      if (!(await frage({ titel: `Kategorie ${stelle.kategorie.name} entfernen?`, folgen, ja: "Kategorie entfernen" }))) return false;
    } catch (e) {
      melde.schlecht(e);
      return false;
    }
    return this.#tue(() => this.#quelle.entferneKategorie(stelle), "Kategorie entfernt");
  }

  async #tue(tun: () => Promise<void>, text: string): Promise<boolean> {
    try {
      await tun();
      melde.gut(text);
      return true;
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
      return false;
    }
  }

  // Der Entwurf als Quelle: jede Änderung geht ganz an den Server und kommt von dort zurück

  #entwurfsquelle: Katalogquelle = {
    speichereBereich: async (alt, angaben) => {
      const bereiche = this.entwurf?.bereiche ?? [];
      // Was das Fenster nicht kennt (Herkunft, Zahl), bleibt, wie es war
      const { kategorien: _kategorien, ...bisher } = alt ?? { kategorien: [] };
      const schluessel = alt?.schluessel ?? neuerBereichsschluessel(bereiche, angaben.name);
      await this.#schreibe(setzeBereich(bereiche, alt?.schluessel ?? null, { anzahl: null, herkunft: "eigen", ...bisher, ...angaben, schluessel }));
    },
    speichereKategorie: async (alt, ziel, felder) => {
      const bereiche = this.entwurf?.bereiche ?? [];
      // Was das Fenster nicht kennt (Teile, Herkunft, Zahl), bleibt, wie es war
      const neu: Katalogkategorie = {
        ...alt?.kategorie,
        ...felder,
        farbe: eigeneFarbe(felder, ziel),
        regeln: regelnAus(felder.regeln),
        schluessel: alt?.kategorie.schluessel ?? neuerKategorieschluessel(bereiche, ziel.schluessel, felder.name),
        herkunft: alt?.kategorie.herkunft ?? "eigen",
        anzahl: alt?.kategorie.anzahl ?? null,
      };
      await this.#schreibe(setzeKategorie(bereiche, alt?.kategorie.schluessel ?? null, ziel.schluessel, neu));
    },
    bereichsfolgen: async (b) => [
      b.kategorien.length ? `${b.name} und ${anzahl(b.kategorien.length, "Kategorie", "Kategorien")} darin fehlen danach im Vorschlag.` : `${b.name} fehlt danach im Vorschlag.`,
      ...this.#bleibt(),
    ],
    kategoriefolgen: async ({ kategorie }) => [`${kategorie.name} fehlt danach im Vorschlag.`, ...this.#bleibt()],
    entferneBereich: async (b) => this.#schreibe(entferneBereich(this.entwurf?.bereiche ?? [], b.schluessel)),
    entferneKategorie: async ({ kategorie }) => this.#schreibe(entferneKategorie(this.entwurf?.bereiche ?? [], kategorie.schluessel)),
  };

  async #schreibe(bereiche: Katalogbereich[]): Promise<void> {
    this.entwurf = (await speichereEntwurf({ bereiche })).entwurf;
  }

  /** Annehmen löscht nie: was im gültigen Katalog steht, bleibt */
  #bleibt(): string[] {
    return this.hatKatalog ? ["Im gültigen Katalog wird dabei nichts gelöscht."] : [];
  }

  #entwurfsumfang(): string {
    const u = umfang(this.entwurf?.bereiche ?? []);
    return `Der Vorschlag mit ${anzahl(u.bereiche, "Bereich", "Bereichen")} und ${anzahl(u.kategorien, "Kategorie", "Kategorien")} geht verloren.`;
  }

  async #ersetzeEntwurf(): Promise<boolean> {
    return frage({ titel: "Vorschlag ersetzen?", folgen: [this.#entwurfsumfang(), "Änderungen daran gehen verloren."], ja: "Ersetzen", symbol: "arrows-rotate" });
  }

  async #verfolge(): Promise<void> {
    if (this.#verfolgt) return;
    this.#verfolgt = true;
    try {
      while (this.passtAn) {
        const l = this.lauf!;
        auftraege.setze({ id: AUFTRAG, titel: TITEL, text: l.schritt || "Läuft", anteil: l.stapel_gesamt ? l.stapel / l.stapel_gesamt : null, laeuft: !l.pause, pausiert: l.pause, weg: WEG });
        await new Promise((r) => setTimeout(r, TAKT_MS));
        try {
          const stand = await ladeEntwurf();
          this.lauf = stand.lauf;
          this.entwurf = stand.entwurf;
        } catch {
          // ohne Antwort bleibt der letzte Stand stehen
        }
      }
      const grund = this.lauf?.grund ?? "";
      const text = this.entwurf ? `Vorschlag fertig, ${anzahl(umfang(this.entwurf.bereiche).bereiche, "Bereich", "Bereiche")}` : "Kein Vorschlag entstanden";
      auftraege.setze({ id: AUFTRAG, titel: TITEL, text: grund ? `${text}. ${grund}` : text, anteil: null, laeuft: false, weg: WEG });
      if (this.entwurf) melde.gut(text);
      if (grund) melde.warn(grund);
    } finally {
      this.#verfolgt = false;
    }
  }
}

export const pflege = new Katalogpflege();
