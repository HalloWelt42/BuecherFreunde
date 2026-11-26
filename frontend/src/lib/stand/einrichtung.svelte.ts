// Der Assistent der Ersteinrichtung (BF-82): Zustand vom Server, welcher Schritt gezeigt wird, Zurück, Weiter und Überspringen.
// Vor der Anmeldung entscheidet er, ob statt der Anmeldung der Assistent kommt; unter Wartung steht er in der Bühne und merkt
// nichts am Server, bis man übernimmt. Was ein Schritt zeigt und tut, steht in ansichten/einrichtung.
import { ladeEinrichtung, oeffneAssistent, schliesseAb, schliesseAssistent, setzeSchritt, waehleAusgangslage, type Einrichtung, type Lagename } from "../api/einrichtung";
import { aktueller, laufVon, nachbar, sichtbar } from "../einrichtung/ablauf";
import { melde } from "./meldungen.svelte";

class Einrichtungsstand {
  zustand = $state<Einrichtung | null>(null);
  geladen = $state(false);
  /** Der gewählte Schritt; leer: der erste offene des Servers */
  gezeigt = $state("");
  /** Zurück vom ersten Schritt zeigt wieder die Ausgangslagen */
  willkommen = $state(false);
  arbeitet = $state(false);

  /** Neue Installation, noch nicht abgeschlossen: statt Anmeldung und Schale kommt der Assistent */
  ersteinrichtung = $derived(!!this.zustand?.zeigen && this.zustand.modus === "neu");
  wartung = $derived(this.zustand?.modus === "wartung");
  lauf = $derived(this.zustand ? laufVon(this.zustand) : null);
  schritte = $derived(sichtbar(this.zustand?.schritte ?? []));
  schritt = $derived(aktueller(this.schritte, this.gezeigt, this.zustand?.schritt ?? null));
  zeigtWillkommen = $derived(this.ersteinrichtung && (!this.zustand?.ausgangslage || this.willkommen));
  /** Zurück vom ersten Schritt geht nur, solange die Ausgangslage noch wählbar ist (neue Installation) */
  ersterSchritt = $derived(!!this.schritt && this.schritte[0]?.schluessel === this.schritt.schluessel);

  async laden(): Promise<void> {
    try {
      this.zustand = await ladeEinrichtung();
    } catch {
      // ohne Antwort gilt, was da ist; die Anmeldung kommt wie bisher
    } finally {
      this.geladen = true;
    }
  }

  nimm(e: Einrichtung): void {
    this.zustand = e;
  }

  /** Eine Arbeit des Assistenten: währenddessen sind die Tasten gesperrt, ein Fehler kommt als Meldung */
  async tu(arbeit: () => Promise<unknown>, fehlertext = "Nicht geklappt"): Promise<boolean> {
    this.arbeitet = true;
    try {
      await arbeit();
      return true;
    } catch (e) {
      melde.schlecht(e, fehlertext);
      return false;
    } finally {
      this.arbeitet = false;
    }
  }

  async waehle(lage: Lagename): Promise<void> {
    this.nimm(await waehleAusgangslage(lage));
    this.willkommen = false;
    this.gezeigt = "";
  }

  zeige(schritt: string): void {
    this.gezeigt = schritt;
    this.willkommen = false;
  }

  zurueck(): void {
    const s = this.schritt;
    if (!s) return;
    const vor = nachbar(this.schritte, s.schluessel, -1);
    if (vor) this.gezeigt = vor;
    else if (this.ersteinrichtung) this.willkommen = true;
  }

  /** Weiter: der Schritt gilt am Server als erledigt (unter Wartung merkt der Server nichts), dann kommt der nächste */
  async weiter(): Promise<void> {
    await this.#setze("erledigt");
  }

  async ueberspringen(): Promise<void> {
    await this.#setze("ueberspringen");
  }

  async #setze(aktion: "erledigt" | "ueberspringen"): Promise<void> {
    const s = this.schritt;
    if (!s) return;
    const schon = aktion === "erledigt" ? s.stand === "erledigt" : s.stand === "uebersprungen";
    if (!this.wartung && !schon) this.nimm(await setzeSchritt(s.schluessel, aktion));
    this.gezeigt = nachbar(this.schritte, s.schluessel, 1) ?? s.schluessel;
  }

  /** Die Ersteinrichtung abschließen; danach kommt die Bibliothek (mit Anmeldung, wenn noch keine gilt) */
  async abschliessen(ziel = "/"): Promise<void> {
    this.nimm(await schliesseAb());
    location.assign(ziel);
  }

  async oeffne(): Promise<void> {
    this.nimm(await oeffneAssistent());
    this.gezeigt = "";
  }

  /** Unter Wartung ohne Übernehmen schließen: alles Vorgemerkte fällt weg */
  async schliesse(): Promise<void> {
    this.nimm(await schliesseAssistent());
    this.gezeigt = "";
  }
}

export const einrichtung = new Einrichtungsstand();
