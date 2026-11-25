// Längere Arbeiten der Wartung: laufen weiter, wenn man die Ansicht verlässt, und stehen oben unter Aufträge
import { pruefeDateien, sicherungAnlegen, sicherungen, type Dateipruefung, type Sicherung } from "../../lib/api/config";
import { indexNeuAufbauen } from "../../lib/api/search";
import { anzahl, groesse, zahl } from "../../lib/format";
import { auftraege } from "../../lib/stand/auftraege.svelte";
import { melde } from "../../lib/stand/meldungen.svelte";

type Vorgang = "sicherung" | "index" | "dateien";

const TITEL: Record<Vorgang, string> = { sicherung: "Sicherung", index: "Suchindex neu aufbauen", dateien: "Dateien prüfen" };
const WEG = "/settings/wartung";

class Vorgaenge {
  laeuft = $state<Record<Vorgang, boolean>>({ sicherung: false, index: false, dateien: false });
  sicherungen = $state<Sicherung[] | null>(null);
  pruefung = $state<Dateipruefung | null>(null);

  async #fuehreAus(v: Vorgang, beginn: string, tun: () => Promise<string>): Promise<void> {
    if (this.laeuft[v]) return;
    this.laeuft[v] = true;
    auftraege.setze({ id: v, titel: TITEL[v], text: beginn, anteil: null, laeuft: true, weg: WEG });
    try {
      const ergebnis = await tun();
      auftraege.setze({ id: v, titel: TITEL[v], text: ergebnis, anteil: null, laeuft: false, weg: WEG });
      melde.gut(ergebnis);
    } catch (e) {
      const grund = e instanceof Error ? e.message : String(e);
      auftraege.setze({ id: v, titel: TITEL[v], text: `Gescheitert: ${grund}`, anteil: null, laeuft: false, weg: WEG });
      melde.schlecht(e, TITEL[v]);
    } finally {
      this.laeuft[v] = false;
    }
  }

  async ladeSicherungen(): Promise<void> {
    try {
      this.sicherungen = await sicherungen();
    } catch {
      this.sicherungen = null;
    }
  }

  sichere(): Promise<void> {
    return this.#fuehreAus("sicherung", "Datenbank und Einstellungen werden gepackt", async () => {
      const s = await sicherungAnlegen();
      await this.ladeSicherungen();
      // Ohne Änderung seit der jüngsten Sicherung entsteht keine neue; die Antwort sagt dann warum
      return s.neu ? `Gesichert: ${s.filename}, ${groesse(s.size)}` : s.message.replace(/Backup/g, "Sicherung");
    });
  }

  baueIndex(): Promise<void> {
    return this.#fuehreAus("index", "Alle Texte werden neu eingelesen", async () => `Suchindex fertig, ${anzahl((await indexNeuAufbauen()).indexiert, "Buch", "Bücher")}`);
  }

  pruefe(): Promise<void> {
    return this.#fuehreAus("dateien", "Jede Datei wird einmal geöffnet", async () => {
      const p = await pruefeDateien();
      this.pruefung = p;
      return `${zahl(p.geprueft)} Dateien geprüft, ${p.defekt ? anzahl(p.defekt, "Auffälligkeit", "Auffälligkeiten") : "alles in Ordnung"}`;
    });
  }
}

export const vorgaenge = new Vorgaenge();
