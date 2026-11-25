// Vorlesen über die App Pappagei und nur darüber: die Seite spricht mit ihrer Browser-Erweiterung (postMessage), die an
// die App weiterreicht. Fehlt sie (etwa am Tablet), gibt es nur einen Hinweis.

export const vorlesen = $state({ aktiv: false, was: "" });

interface Antwort {
  type?: string;
  id?: number;
  ok?: boolean;
}

const wartend = new Map<number, (antwort: Antwort) => void>();
let naechste = 1;
const HOECHSTENS = 49_000;

if (typeof window !== "undefined") {
  window.addEventListener("message", (e: MessageEvent<Antwort>) => {
    if (e.source !== window || e.data?.type !== "pappagei-ack" || !e.data.id) return;
    const fertig = wartend.get(e.data.id);
    wartend.delete(e.data.id);
    fertig?.(e.data);
  });
}

function rufe(action: string, mehr: Record<string, unknown> = {}, fristMs = 1200): Promise<Antwort | null> {
  return new Promise((r) => {
    const id = naechste++;
    const uhr = setTimeout(() => {
      wartend.delete(id);
      r(null);
    }, fristMs);
    wartend.set(id, (antwort) => {
      clearTimeout(uhr);
      r(antwort);
    });
    window.postMessage({ type: "pappagei", action, id, ...mehr }, "*");
  });
}

export const NICHT_DA = "Pappagei antwortet nicht. Läuft die App, und ist die Erweiterung aktuell (ab 0.4.0)?";

/** Liest vor; false, wenn die App nicht übernommen hat. */
export async function sprich(text: string, was: string): Promise<boolean> {
  const sauber = text.trim();
  if (!sauber) return false;
  const antwort = await rufe("speak", { text: sauber.slice(0, HOECHSTENS) });
  vorlesen.aktiv = !!antwort?.ok;
  vorlesen.was = vorlesen.aktiv ? was : "";
  return vorlesen.aktiv;
}

export function schweige(): void {
  if (!vorlesen.aktiv) return;
  void rufe("stop", {}, 500);
  vorlesen.aktiv = false;
  vorlesen.was = "";
}
