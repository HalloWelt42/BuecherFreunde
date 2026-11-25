// Vorlesen über die App Pappagei: die Seite spricht mit ihrer Browser-Erweiterung (postMessage), die an die App weiterreicht.
import type { Beobachter, Vorleser } from "./typen";

interface Antwort {
  type?: string;
  id?: number;
  ok?: boolean;
}

const HOECHSTENS = 49_000;
const FEHLT = "Pappagei antwortet nicht. Läuft die App, und ist die Erweiterung aktuell (ab 0.4.0)?";

export class Pappagei implements Vorleser {
  #wartend = new Map<number, (antwort: Antwort) => void>();
  #naechste = 1;
  #horcht = false;

  #horche(): void {
    if (this.#horcht) return;
    this.#horcht = true;
    addEventListener("message", (e: MessageEvent<Antwort>) => {
      if (e.source !== window || e.data?.type !== "pappagei-ack" || !e.data.id) return;
      const fertig = this.#wartend.get(e.data.id);
      this.#wartend.delete(e.data.id);
      fertig?.(e.data);
    });
  }

  #rufe(action: string, mehr: Record<string, unknown> = {}, fristMs = 1200): Promise<Antwort | null> {
    this.#horche();
    return new Promise((r) => {
      const id = this.#naechste++;
      const uhr = setTimeout(() => {
        this.#wartend.delete(id);
        r(null);
      }, fristMs);
      this.#wartend.set(id, (antwort) => {
        clearTimeout(uhr);
        r(antwort);
      });
      window.postMessage({ type: "pappagei", action, id, ...mehr }, "*");
    });
  }

  entsperre(): void {}

  lies(text: string, _stimme: string, bei: Beobachter): void {
    bei.wartet();
    void this.#rufe("speak", { text: text.trim().slice(0, HOECHSTENS) }).then((antwort) => (antwort?.ok ? bei.klingt() : bei.fehler(FEHLT)));
  }

  halt(): void {
    void this.#rufe("stop", {}, 500);
  }
}
