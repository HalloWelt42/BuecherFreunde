// Warum sich ein Buch nicht laden ließ, in den Worten des Servers. Die Meldung der Lesebibliothek kommt nie auf den Schirm:
// sie ist englisch und nennt Adressen.
import { anfrage, ApiError } from "../api/client";
import { dateiUrl } from "../api/books";

export interface Ladefehler {
  text: string;
  /** Gibt der Server die Datei her? Dann hilft Öffnen im Browser oder Herunterladen. */
  dateiDa: boolean;
}

export async function ladefehler(buch: number): Promise<Ladefehler> {
  try {
    const antwort = await anfrage(dateiUrl(buch), { headers: { Range: "bytes=0-0" } });
    await antwort.body?.cancel();
    return { text: "Die Datei ließ sich nicht lesen", dateiDa: true };
  } catch (grund) {
    return { text: grund instanceof ApiError ? grund.message : "Keine Verbindung zur Bibliothek", dateiDa: false };
  }
}
