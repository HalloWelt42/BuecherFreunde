// Eine Sicherung in Teilen hochladen (BF-82), fortsetzbar wie bei der Annahme: erst die Prüfsumme, dann anmelden (gleicher Name,
// Größe und Prüfsumme finden den angefangenen Stand wieder) und Teil für Teil ab dem Stand des Servers. Ohne Oberfläche; Dienst,
// Prüfsumme und Wartezeiten kommen von außen und lassen sich im Test ersetzen.
import { ApiError } from "../api/client";
import type { Hochladestand } from "../api/einrichtung";

export interface Sicherungsdienst {
  anmelden(name: string, groesse: number, sha256: string): Promise<Hochladestand>;
  teil(id: string, ab: number, teil: Blob, abbruch: AbortSignal): Promise<Hochladestand>;
  stand(id: string): Promise<Hochladestand>;
}

export type Pruefsumme = (datei: Blob, fortschritt: (anteil: number) => void, abbruch: AbortSignal) => Promise<string>;

export interface Ladestand {
  lage: "prueft" | "laedt" | "wartet" | "fertig";
  /** 0 bis 1 */
  anteil: number;
  text: string;
}

export interface Ladeoptionen {
  /** Wartezeiten nach einem Abriss; danach gibt das Hochladen auf */
  pausenMs?: number[];
  warte?: (ms: number) => Promise<void>;
}

const abriss = (e: unknown) => e instanceof ApiError && (e.status === 0 || e.status >= 500 || e.status === 429);

/** Lädt die Datei hoch und liefert den fertigen Stand; ein Fehler des Servers (etwa die Prüfsumme, 422) geht weiter hinaus */
export async function ladeSicherungHoch(datei: File, dienst: Sicherungsdienst, pruefsumme: Pruefsumme, melde: (s: Ladestand) => void,
  abbruch: AbortSignal, optionen: Ladeoptionen = {}): Promise<Hochladestand> {
  const pausen = optionen.pausenMs ?? [1000, 3000, 8000, 20000];
  const warte = optionen.warte ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  melde({ lage: "prueft", anteil: 0, text: "Prüfsumme wird gerechnet" });
  const sha = await pruefsumme(datei, (anteil) => melde({ lage: "prueft", anteil, text: "Prüfsumme wird gerechnet" }), abbruch);
  let h = await dienst.anmelden(datei.name, datei.size, sha);
  let versuche = 0;
  while (!h.fertig) {
    abbruch.throwIfAborted();
    melde({ lage: "laedt", anteil: h.empfangen / datei.size, text: "Wird hochgeladen" });
    try {
      h = await dienst.teil(h.id, h.empfangen, datei.slice(h.empfangen, Math.min(datei.size, h.empfangen + h.teil_groesse)), abbruch);
      versuche = 0;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && typeof e.data?.empfangen === "number") {
        h = { ...h, empfangen: e.data.empfangen };
        continue;
      }
      if (!abriss(e) || versuche >= pausen.length) throw e;
      melde({ lage: "wartet", anteil: h.empfangen / datei.size, text: "Keine Verbindung, gleich geht es weiter" });
      await warte(pausen[versuche++]);
      h = await dienst.stand(h.id).catch(() => h);
    }
  }
  melde({ lage: "fertig", anteil: 1, text: "Hochgeladen, Prüfsumme stimmt" });
  return h;
}
