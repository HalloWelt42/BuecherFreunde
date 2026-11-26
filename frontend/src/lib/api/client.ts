/**
 * API-Client mit Bearer Token Auth, Fehlerbehandlung und SSE-Support.
 */

import { sprich } from "../hintergrund";
import { netz } from "../stand/netz.svelte";

const SCHLUESSEL = "api_token";

// Die Anmeldung liegt im Speicher des Browsers (je Adresse geteilt von allen Tabs) und wird bei jeder Anfrage frisch
// gelesen: meldet man sich in einem Tab an, gilt das sofort für alle (etwa einen Leser, der aus dem Assistenten an einer
// Seite geöffnet wurde und noch die Anmeldung zeigt).
let apiToken = lesen() ?? "";

/** @returns {string | null} null, wenn es keinen Speicher gibt (dann gilt der Wert dieser Seite) */
function lesen(): string | null {
  try {
    return localStorage.getItem(SCHLUESSEL) || "";
  } catch {
    return null;
  }
}

/** Callback wenn Token ungültig ist - wird von App.svelte gesetzt */
let onAuthRequired: (() => void) | null = null;

/**
 * Registriert einen Callback für fehlende/ungültige Authentifizierung.
 */
export function onAuthError(callback: () => void): void {
  onAuthRequired = callback;
}

/**
 * Prüft ob ein Token gespeichert ist.
 */
export function hasToken(): boolean {
  return getToken().length > 0;
}

/**
 * Ein anderer Tab hat sich an- oder abgemeldet.
 */
export function beiTokenWechsel(tun: (token: string) => void): void {
  addEventListener("storage", (e) => {
    if (e.key === SCHLUESSEL) {
      apiToken = e.newValue || "";
      tun(apiToken);
    }
  });
}

/**
 * Setzt den API-Token für alle Requests.
 */
export function setToken(token: string): void {
  apiToken = token;
  try {
    if (token) localStorage.setItem(SCHLUESSEL, token);
    else localStorage.removeItem(SCHLUESSEL);
  } catch {
    // ohne Speicher gilt die Anmeldung nur für diese Seite
  }
}

/**
 * Abmelden: beendet die Sitzung in der Kellerwolke (auf einem gekoppelten Gerät trennt es das Gerät).
 */
export async function abmelden(): Promise<void> {
  try {
    await fetch("/api/anmeldung/abmelden", {
      method: "POST",
      headers: { "X-Kellerwolke-Sitzung": getToken() },
    });
  } catch {
    // egal: lokal ist man danach abgemeldet
  }
  setToken("");
  vergissLesestoff();
  if (onAuthRequired) onAuthRequired();
}

/** Die Meldung des Servers: `detail` ist ein Satz, bei Prüffehlern (422) eine Liste mit `msg` je Feld */
export function meldungAus(detail: unknown): string {
  if (typeof detail === "string") return detail;
  const eine = (d: unknown) => (typeof d === "string" ? d : d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : "");
  if (Array.isArray(detail)) return [...new Set(detail.map(eine).filter(Boolean))].join("; ");
  return eine(detail);
}

/** Die für das Lesen ohne Netz gemerkten Bücher gehören dem, der abgemeldet ist */
function vergissLesestoff(): void {
  void sprich({ art: "abgemeldet" });
}

/**
 * Öffnet die Inhalte für Adressen, die keinen Kopf senden können (Bilder, Dateien, Ereignisströme): der Server setzt ein
 * Cookie, das nur er liest. So steht die Anmeldung nie in einer Adresse.
 */
export async function oeffneInhalte(): Promise<void> {
  try {
    await anfrage("/api/anmeldung/zugang", { method: "POST" });
  } catch {
    // abgewiesen: die Anmeldung erscheint von selbst; ohne Verbindung versucht es der nächste Start
  }
}

/**
 * Gibt den aktuellen Token zurück.
 */
export function getToken(): string {
  apiToken = lesen() ?? apiToken;
  return apiToken;
}

/**
 * API-Fehler mit Statuscode und Nachricht.
 */
export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: any) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Basis-Fetch mit Auth-Header und Fehlerbehandlung.
 */
export async function anfrage(path: string, options: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };

  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
    headers["X-Kellerwolke-Sitzung"] = token;
  }

  if (
    options.body &&
    typeof options.body === "string" &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(path, { ...options, headers });
  } catch (grund) {
    if (grund instanceof DOMException && grund.name === "AbortError") throw grund;
    netz.fort();
    throw new ApiError(0, "Keine Verbindung zur Bibliothek");
  }
  netz.da();

  if (!response.ok) {
    let data = null;
    try {
      data = await response.json();
    } catch {
      // Response ohne JSON-Body
    }

    // Nur eine abgewiesene Anmeldung (401) führt zur Anmeldung; 403 heißt "nicht erlaubt" und meldet nie ab
    if (response.status === 401 && onAuthRequired) {
      onAuthRequired();
    }

    const message = meldungAus(data?.detail) || `HTTP ${response.status}`;
    throw new ApiError(response.status, message, data);
  }

  return response;
}

/**
 * GET-Request mit JSON-Antwort.
 */
export type Parameter = Record<string, string | number | boolean | null | undefined>;

export async function get<T = any>(path: string, params?: Parameter): Promise<T> {
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value != null && value !== "") {
        searchParams.set(key, String(value));
      }
    }
    const qs = searchParams.toString();
    if (qs) {
      path += `?${qs}`;
    }
  }
  const response = await anfrage(path);
  return response.json();
}

/**
 * POST-Request mit JSON-Body.
 */
export async function post<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await anfrage(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return response.json();
}

/**
 * PATCH-Request mit JSON-Body.
 */
export async function patch<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await anfrage(path, {
    method: "PATCH",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return response.json();
}

/**
 * PUT-Request mit JSON-Body: ersetzt einen Wert ganz.
 */
export async function put<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await anfrage(path, {
    method: "PUT",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return response.json();
}

/**
 * DELETE-Request.
 */
export async function del<T = any>(path: string): Promise<T> {
  const response = await anfrage(path, { method: "DELETE" });
  return response.json();
}

/**
 * Datei-Upload via FormData.
 */
let laufendeUploads = 0;

/** Das Hochladen in Teilen (lib/annahme) meldet hier Beginn und Ende. */
export function hochladenZaehlen(schritt: number): void {
  laufendeUploads = Math.max(0, laufendeUploads + schritt);
}

/** Läuft gerade ein Hochladen? (dann lädt die Seite für eine neue Fassung nicht neu) */
export function hochladenLaeuft(): boolean {
  return laufendeUploads > 0;
}

export async function upload<T = any>(path: string, formData: FormData): Promise<T> {
  laufendeUploads++;
  try {
    const response = await anfrage(path, {
      method: "POST",
      body: formData,
      // Content-Type wird automatisch mit Boundary gesetzt
    });
    return response.json();
  } finally {
    laufendeUploads--;
  }
}

/**
 * SSE-Verbindung für Echtzeit-Events.
 */
export function sse(path: string, onEvent: (e: { type: string; data: any }) => void, onError?: (fehler: Error) => void): { close: () => void } {
  const source = new EventSource(path);

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onEvent({ type: "message", data });
    } catch {
      onEvent({ type: "message", data: event.data });
    }
  };

  source.onerror = () => {
    if (onError) {
      onError(new Error("SSE-Verbindung fehlgeschlagen"));
    }
    source.close();
  };

  return {
    close() {
      source.close();
    },
  };
}

/**
 * Datei-Download (z.B. Buchcover, Buchdatei).
 */
export async function download(path: string): Promise<Blob> {
  const response = await anfrage(path);
  return response.blob();
}
