// Die gedruckte Seitenzahl zu einer PDF-Seite: aus der Datei, sonst fragt der Leser nach kurzer Ruhe den Server
import { textSeiten } from "../../api/books";
import { gedruckteSeite, type PdfBuch } from "./dokument";

const RUHE_MS = 900;

export class Gedruckt {
  zahl = $state("");

  constructor(private buch: number) {}

  /** Zu dieser Seite; liefert, was beim Weiterblättern zu lösen ist */
  folge(pdf: PdfBuch | null, nr: number): (() => void) | undefined {
    const ausDatei = pdf ? gedruckteSeite(pdf, nr) : "";
    this.zahl = ausDatei;
    if (ausDatei || pdf?.beschriftung) return undefined;
    let gilt = true;
    const uhr = setTimeout(async () => {
      const antwort = await textSeiten(this.buch, nr, 1).catch(() => null);
      const wert = antwort?.seiten?.[0]?.gedruckt ?? "";
      if (gilt && wert && wert !== String(nr)) this.zahl = wert;
    }, RUHE_MS);
    return () => {
      gilt = false;
      clearTimeout(uhr);
    };
  }
}
