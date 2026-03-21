/**
 * Store für Hintergrundprozesse - Import, AI-Scan, Indizierung.
 * Pollt regelmäßig den Import-Status und stellt ihn global bereit.
 * Benachrichtigt registrierte Listener bei neuen fertigen Imports.
 */

import { get } from "../api/client.js";

let _pollInterval = null;
let _lastFertigCount = 0;

/** @type {Array<() => void>} */
let _onChangeCallbacks = [];

export const processes = $state({
  /** @type {Array<{id: number, filename: string, status: string, progress_percent: number, current_step: string, error: string, book_id: number|null}>} */
  importTasks: [],

  /** Ob gerade aktiv gepollt wird */
  polling: false,

  /** Fussleiste ein-/ausklappen */
  expanded: false,

  /** Letzte Aktualisierung */
  lastUpdate: null,
});

/** Berechnete Werte */
export function getProcessStats() {
  const tasks = processes.importTasks;
  const fertig = tasks.filter((t) => t.status === "fertig").length;
  const fehler = tasks.filter((t) => t.status === "fehler").length;
  const duplikat = tasks.filter((t) => t.status === "duplikat").length;
  const aktiv = tasks.filter(
    (t) => t.status === "wartend" || t.status === "verarbeite",
  ).length;
  const gesamt = tasks.length;
  const prozent =
    gesamt > 0 ? Math.round(((fertig + duplikat) / gesamt) * 100) : 0;
  const aktuell = tasks.find((t) => t.status === "verarbeite");

  return { fertig, fehler, duplikat, aktiv, gesamt, prozent, aktuell };
}

/**
 * Callback registrieren der aufgerufen wird wenn neue Bücher importiert wurden.
 * @param {() => void} cb
 * @returns {() => void} Unsubscribe-Funktion
 */
export function onBooksChanged(cb) {
  _onChangeCallbacks.push(cb);
  return () => {
    _onChangeCallbacks = _onChangeCallbacks.filter((c) => c !== cb);
  };
}

/** Import-Status einmalig abfragen */
export async function fetchImportStatus() {
  try {
    const data = await get("/api/import/status");
    processes.importTasks = data.aufgaben || [];
    processes.lastUpdate = new Date();

    // Prüfen ob neue Bücher fertig wurden
    const stats = getProcessStats();
    if (stats.fertig > _lastFertigCount && _lastFertigCount > 0) {
      // Listener benachrichtigen
      for (const cb of _onChangeCallbacks) {
        try {
          cb();
        } catch {
          /* ignore */
        }
      }
    }
    _lastFertigCount = stats.fertig;
  } catch {
    // Fehler ignorieren - Polling laeuft weiter
  }
}

/** Polling starten (1.5s Intervall wenn aktiv, 10s wenn idle) */
export function startPolling() {
  if (_pollInterval) return;
  processes.polling = true;

  async function poll() {
    await fetchImportStatus();
    const stats = getProcessStats();

    if (stats.aktiv > 0) {
      _pollInterval = setTimeout(poll, 1500);
    } else {
      _pollInterval = setTimeout(poll, 10000);
    }
  }

  poll();
}

/** Polling stoppen */
export function stopPolling() {
  if (_pollInterval) {
    clearTimeout(_pollInterval);
    _pollInterval = null;
  }
  processes.polling = false;
}

/** Fussleiste togglen */
export function toggleExpanded() {
  processes.expanded = !processes.expanded;
}

/** Fertige und fehlerhafte Tasks aus der Liste entfernen */
export function clearFinished() {
  processes.importTasks = processes.importTasks.filter(
    (t) => t.status === "wartend" || t.status === "verarbeite",
  );
  if (processes.importTasks.length === 0) {
    processes.expanded = false;
  }
}
