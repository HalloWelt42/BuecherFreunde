// Gespräch mit dem Dienst im Hintergrund (public/sw.js): eine Nachricht, eine Antwort. Ohne Dienst (Entwicklung, kein https)
// gibt es keine Antwort, dann null.
export interface Gemerktesbuch {
  id: number;
  titel: string;
  bytes: number;
  zeit: number;
}

/** Ohne Netz lesen: die Wahl des Geräts, was gemerkt ist und die Grenzen des Dienstes */
export interface Lesestoffstand {
  an: boolean;
  buecher: Gemerktesbuch[];
  bytes: number;
  grenzen: { buecher: number; bytes: number };
}

export type Nachricht = { art: "lesestoff" } | { art: "lesestoff-an"; an: boolean } | { art: "lesestoff-leeren" } | { art: "abgemeldet" };

const FRIST_MS = 5000;

export async function sprich(nachricht: Nachricht): Promise<Lesestoffstand | null> {
  if (typeof navigator === "undefined" || !navigator.serviceWorker) return null;
  const dienst = (await navigator.serviceWorker.getRegistration().catch(() => undefined))?.active;
  if (!dienst) return null;
  return new Promise((fertig) => {
    const kanal = new MessageChannel();
    const uhr = setTimeout(() => fertig(null), FRIST_MS);
    kanal.port1.onmessage = (e) => {
      clearTimeout(uhr);
      fertig((e.data as Lesestoffstand | null) ?? null);
    };
    dienst.postMessage(nachricht, [kanal.port2]);
  });
}
