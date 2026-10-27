/**
 * Neue Fassung auf dem Server: die Seite lädt von selbst neu, nie ein hartes Neuladen von Hand.
 *
 * Die Startseite kommt ohne Zwischenspeicher (nginx), Skripte und Gestaltung tragen Prüfsummen im Namen. Die
 * Oberfläche kennt ihre eigene Fassung (beim Bau aus VERSION eingesetzt) und vergleicht sie mit der des Servers:
 * beim Start, jede Minute und wenn das Fenster wieder nach vorn kommt. Weicht sie ab, lädt die Seite in den ersten
 * Sekunden nach dem Start sofort neu, später beim nächsten Ortswechsel oder wenn das Fenster nach vorn kommt; nie
 * während Vorlesen oder Hochladen. Je Serverfassung nur ein selbsttätiger Versuch (Merker in der Sitzung), damit ein
 * hängender Zwischenspeicher keine Schleife auslöst; dazwischen zeigt ein Band einen Knopf.
 */
import { tts } from "./stores/tts.svelte.js";
import { hochladenLaeuft } from "./api/client.js";

export const OBERFLAECHE_FASSUNG = __FASSUNG__;
const MERKER = "buecherfreunde.neu_geladen";
const START_FENSTER_MS = 10_000;
const PRUEFEN_MS = 60_000;

export const fassung = $state({ neu: null });

/** Nichts, was ein Neuladen abbrechen würde. */
function ruhig() {
  return !tts.aktiv && !hochladenLaeuft();
}

function erlaubt(neu) {
  try {
    if (sessionStorage.getItem(MERKER) === neu) return false;
    sessionStorage.setItem(MERKER, neu);
  } catch {
    // ohne Sitzungsspeicher kein Merker: dann lieber einmal laden als nie
  }
  return true;
}

/** @param {"start" | "takt" | "ortswechsel" | "sichtbar"} anlass */
export function vielleichtNeuLaden(anlass) {
  const neu = fassung.neu;
  if (!neu || anlass === "takt" || !ruhig()) return;
  if (anlass === "start" && performance.now() > START_FENSTER_MS) return;
  if (erlaubt(neu)) location.reload();
}

async function pruefen(anlass) {
  try {
    const antwort = await fetch("/api/config/version", { cache: "no-store" });
    if (!antwort.ok) return;
    const { version } = await antwort.json();
    fassung.neu = version && version !== OBERFLAECHE_FASSUNG ? version : null;
  } catch {
    return;
  }
  vielleichtNeuLaden(anlass);
}

function sichtbar() {
  if (document.visibilityState === "visible") pruefen("sichtbar");
}

/** Vergleich starten; liefert das Aufräumen. */
export function fassungVerfolgen() {
  // Der Entwicklungsserver liefert ohnehin frisch und lädt selbst neu
  if (import.meta.env.DEV) return () => {};
  pruefen("start");
  const takt = setInterval(() => pruefen("takt"), PRUEFEN_MS);
  document.addEventListener("visibilitychange", sichtbar);
  return () => {
    clearInterval(takt);
    document.removeEventListener("visibilitychange", sichtbar);
  };
}
