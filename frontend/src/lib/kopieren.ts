// Text in die Zwischenablage: über die Schnittstelle des Browsers, wo sie fehlt (ohne sichere Verbindung) über eine
// unsichtbare Auswahl. Meldet, ob es geklappt hat.
import { melde } from "./stand/meldungen.svelte";

export async function kopiere(text: string, meldung = "Kopiert"): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else if (!ueberAuswahl(text)) throw new Error("Die Zwischenablage ist hier gesperrt");
    melde.gut(meldung);
    return true;
  } catch (e) {
    if (ueberAuswahl(text)) {
      melde.gut(meldung);
      return true;
    }
    melde.schlecht(e, "Nicht kopiert");
    return false;
  }
}

function ueberAuswahl(text: string): boolean {
  const feld = document.createElement("textarea");
  feld.value = text;
  feld.setAttribute("readonly", "");
  Object.assign(feld.style, { position: "fixed", opacity: "0", pointerEvents: "none" });
  document.body.append(feld);
  feld.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    feld.remove();
  }
}
