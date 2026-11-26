// Die gedruckte Seitenzahl zu einer PDF-Seite: aus der Datei, sonst fragt der Leser nach kurzer Ruhe den Server
import { textSeiten } from "../../api/books";
import { gedruckteSeite, type PdfBuch } from "./dokument";

const RUHE_MS = 900;

export class Gedruckt {
  zahl = $state("");

  /** buch: null, wo der Server den Text der Datei nicht kennt (weiteres Format, Begleitmaterial): dann nur aus der Datei */
  constructor(private buch: number | null) {}

  /** Zu dieser Seite; liefert, was beim Weiterblättern zu lösen ist */
  folge(pdf: PdfBuch | null, nr: number): (() => void) | undefined {
    const ausDatei = pdf ? gedruckteSeite(pdf, nr) : "";
    this.zahl = ausDatei;
    if (ausDatei || pdf?.beschriftung || this.buch === null) return undefined;
    let gilt = true;
    const uhr = setTimeout(async () => {
      const antwort = this.buch === null ? null : await textSeiten(this.buch, nr, 1).catch(() => null);
      const wert = antwort?.seiten?.[0]?.gedruckt ?? "";
      if (gilt && wert && wert !== String(nr)) this.zahl = wert;
    }, RUHE_MS);
    return () => {
      gilt = false;
      clearTimeout(uhr);
    };
  }
}
