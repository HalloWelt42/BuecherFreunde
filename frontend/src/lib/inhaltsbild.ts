// Bilder aus Inhalten (Abbildungen der Textansicht, Bilder im Buch, Umschläge) lädt der Browser ohne Kopfdaten; sie brauchen das
// Cookie für Inhalte, das die App beim Start setzt (BF-102). Fehlt es (abgelaufen, oder beim Start ging es nicht), lädt ein Bild
// nicht. Dann erneuert dieser Baustein einmal den Zugang und lädt das Bild neu; erst wenn es danach nicht kommt, gibt er auf.
import { zugangErneuern } from "./api/client";

/** Merkmal der neu geladenen Adresse: der Server übergeht es, der Browser fragt dadurch wirklich neu */
export const NEU_GELADEN = "zugang";

export function inhaltsbild(bild: HTMLImageElement, aufgeben?: () => void) {
  let versucht = false;
  let bei = aufgeben;
  const fehler = async () => {
    if (versucht || !bild.src || bild.src.startsWith("data:")) return void bei?.();
    versucht = true;
    await zugangErneuern();
    const u = new URL(bild.src, location.href);
    u.searchParams.set(NEU_GELADEN, String(Date.now()));
    bild.src = u.href;
  };
  const geladen = () => (versucht = false);
  bild.addEventListener("error", fehler);
  bild.addEventListener("load", geladen);
  return {
    update(neu?: () => void) {
      bei = neu;
    },
    destroy() {
      bild.removeEventListener("error", fehler);
      bild.removeEventListener("load", geladen);
    },
  };
}
