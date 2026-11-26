// Was die Ansichten einer Übersetzung (Auftrag, Prüfbericht, Begriffsliste) gemeinsam brauchen: das Buch und seine deutsche
// Fassung, sobald es eine gibt
import { holeBuch } from "../../lib/api/books";
import { holeFassungen } from "../../lib/api/uebersetzung";
import type { BuchEinzeln } from "../../lib/typen";
import type { Uebersetzung } from "../../lib/uebersetzung/typen";

export class Buchuebersetzung {
  buch = $state<BuchEinzeln | null>(null);
  deutsch = $state<Uebersetzung | null>(null);
  fehler = $state("");
  geladen = $state(false);

  constructor(public readonly id: number) {}

  async laden(): Promise<void> {
    this.fehler = "";
    try {
      const [buch, liste] = await Promise.all([holeBuch(this.id), holeFassungen(this.id)]);
      this.buch = buch;
      this.deutsch = (liste.find((f) => !f.original && f.sprache === "de") as Uebersetzung | undefined) ?? null;
    } catch (e) {
      this.fehler = e instanceof Error ? e.message : String(e);
    }
    this.geladen = true;
  }
}
