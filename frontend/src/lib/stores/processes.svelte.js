/**
 * Store für Hintergrundprozesse - Import, AI-Scan, Indizierung.
 * Pollt regelmäßig den Import-Status und stellt ihn global bereit.
 * Benachrichtigt registrierte Listener bei neuen fertigen Imports.
 */

import { get } from "../api/client.js";
import { bereinigeImportTasks, holeRescanStatus } from "../api/imports.js";

let _pollInterval = null;
let _lastFertigCount = 0;

/** @type {Array<() => void>} */
let _onChangeCallbacks = [];

export const processes = $state({
  /** @type {Array<{id: number, filename: string, status: string, progress_percent: number, current_step: string, error: string, book_id: number|null}>} */
  importTasks: [],

  /** Echte Zaehler vom Backend (gesamt, wartend, verarbeite, fertig, fehler, duplikat) */
  zaehler: { gesamt: 0, wartend: 0, verarbeite: 0, fertig: 0, fehler: 0, duplikat: 0 },

  /** Rescan-Status vom Backend */
  rescan: {
    laeuft: false,
    typ: "",
    gesamt: 0,
    fortschritt: 0,
    aktuelles_buch: "",
    cover_gefunden: 0,
    isbn_gefunden: 0,
    metadaten_aktualisiert: 0,
    volltext_extrahiert: 0,
    fehler: 0,
  },

  /** Ob gerade aktiv gepollt wird */
  polling: false,

  /** Fussleiste ein-/ausklappen */
  expanded: false,

  /** Letzte Aktualisierung */
  lastUpdate: null,
});

/** Berechnete Werte - nutzt echte Zaehler vom Backend */
export function getProcessStats() {
  const z = processes.zaehler;
  const gesamt = z.gesamt || 0;
  const fertig = z.fertig || 0;
  const fehler = z.fehler || 0;
  const duplikat = z.duplikat || 0;
  const wartend = z.wartend || 0;
  const verarbeite = z.verarbeite || 0;
  const aktiv = wartend + verarbeite;
  const verbleibend = wartend + verarbeite;
  const prozent = gesamt > 0 ? Math.round(((fertig + duplikat) / gesamt) * 100) : 0;
  const aktuell = processes.importTasks.find((t) => t.status === "verarbeite");

  return { fertig, fehler, duplikat, aktiv, wartend, verarbeite, verbleibend, gesamt, prozent, aktuell };
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

/** Listener manuell benachrichtigen (z.B. nach Favorit/Lesesofa-Toggle) */
export function notifyBooksChanged() {
  for (const cb of _onChangeCallbacks) {
    try { cb(); } catch { /* ignore */ }
  }
}

/** Import-Status und Rescan-Status einmalig abfragen */
export async function fetchImportStatus() {
  try {
    const [importData, rescanData] = await Promise.all([
      get("/api/import/status"),
      holeRescanStatus().catch(() => null),
    ]);

    processes.importTasks = importData.aufgaben || [];
    if (importData.zaehler) {
      processes.zaehler = importData.zaehler;
    }
    if (rescanData) {
      processes.rescan = rescanData;
    }
    processes.lastUpdate = new Date();

    // Prüfen ob neue Bücher fertig wurden
    const stats = getProcessStats();
    if (stats.fertig > _lastFertigCount && _lastFertigCount > 0) {
      for (const cb of _onChangeCallbacks) {
        try { cb(); } catch { /* ignore */ }
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
    const rescanAktiv = processes.rescan.laeuft;

    if (stats.aktiv > 0 || rescanAktiv) {
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

/** Fertige und fehlerhafte Tasks aus der DB und Liste entfernen */
export async function clearFinished() {
  try {
    const result = await bereinigeImportTasks();
    processes.importTasks = result.aufgaben || [];
    if (result.zaehler) processes.zaehler = result.zaehler;
    _lastFertigCount = 0;
  } catch {
    // Fallback: nur lokal bereinigen
    processes.importTasks = processes.importTasks.filter(
      (t) => t.status === "wartend" || t.status === "verarbeite",
    );
  }
  if (processes.importTasks.length === 0) {
    processes.expanded = false;
  }
}
