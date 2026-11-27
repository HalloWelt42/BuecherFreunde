/**
 * API-Client mit Bearer Token Auth, Fehlerbehandlung und SSE-Support.
 */

import { sprich } from "../hintergrund";
import { netz } from "../stand/netz.svelte";

const SCHLUESSEL = "api_token";
// Das gewählte Profil (BF-78): sein Schlüssel geht in jeder Anfrage im Kopf X-Profil mit und bleibt auf dem Gerät, bis
// gewechselt wird; die zufällige Kennung des Geräts im Kopf X-Geraet bleibt immer (Bindung an ein Kind, Sitzungen).
const PROFIL = "profil_schluessel";
const GERAET = "geraet_kennung";

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

/** 401 mit diesem `code` (und WWW-Authenticate: Profil): das Gerät bleibt angemeldet, es fehlt nur ein gültiges Profil (BF-78) */
export const PROFIL_WAEHLEN = "profil_waehlen";

let onProfilRequired: (() => void) | null = null;

/** Registriert, was geschieht, wenn der Server ein Profil verlangt: zur Profilwahl, nie abmelden */
export function onProfilFehlt(callback: () => void): void {
  onProfilRequired = callback;
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

/** Ohne Speicher im Browser gelten Profil und Kennung nur für diese Seite */
let profilOhneSpeicher = "";
let geraetOhneSpeicher = "";

/** Der Schlüssel des gewählten Profils; leer: keins gewählt */
export function getProfil(): string {
  try {
    return localStorage.getItem(PROFIL) || "";
  } catch {
    return profilOhneSpeicher;
  }
}

/** Merkt den Schlüssel des gewählten Profils; leer vergisst ihn (Wechsel, Abmelden) */
export function setProfil(schluessel: string): void {
  profilOhneSpeicher = schluessel;
  try {
    if (schluessel) localStorage.setItem(PROFIL, schluessel);
    else localStorage.removeItem(PROFIL);
  } catch {
    // ohne Speicher gilt die Wahl nur für diese Seite
  }
}

/** Ein anderer Tab hat das Profil gewechselt */
export function beiProfilWechsel(tun: (schluessel: string) => void): void {
  addEventListener("storage", (e) => {
    if (e.key === PROFIL) tun(e.newValue || "");
  });
}

/** Zufällige Kennung dieses Browsers, beim ersten Mal erzeugt */
export function geraetKennung(): string {
  let kennung = "";
  try {
    kennung = localStorage.getItem(GERAET) || "";
  } catch {
    kennung = geraetOhneSpeicher;
  }
  if (kennung) return kennung;
  kennung = zufallsKennung();
  geraetOhneSpeicher = kennung;
  try {
    localStorage.setItem(GERAET, kennung);
  } catch {
    // ohne Speicher gilt die Kennung für diese Seite
  }
  return kennung;
}

/** UUID der Version 4; crypto.randomUUID gibt es nur über https, getRandomValues überall */
function zufallsKennung(): string {
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
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
  setProfil("");
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
  const profil = getProfil();
  if (profil) headers["X-Profil"] = profil;
  headers["X-Geraet"] = geraetKennung();

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

    // Nur eine abgewiesene Anmeldung (401) führt zur Anmeldung; 403 heißt "nicht erlaubt" und meldet nie ab. Fehlt nur das
    // Profil, bleibt das Gerät angemeldet und es geht zur Profilwahl.
    const profilFehlt = response.status === 401 && (data?.code === PROFIL_WAEHLEN || /\bProfil\b/.test(response.headers?.get?.("WWW-Authenticate") ?? ""));
    if (profilFehlt) onProfilRequired?.();
    else if (response.status === 401 && onAuthRequired) {
      onAuthRequired();
    }

    const message = meldungAus(data?.detail) || `HTTP ${response.status}`;
    throw new ApiError(response.status, message, data);
  }

  return response;
}

/** Der Inhalt einer Antwort; 204 und ausdrücklich leere Antworten haben keinen */
function inhalt<T>(response: Response): Promise<T> {
  if (response.status === 204 || response.headers?.get?.("Content-Length") === "0") return Promise.resolve(undefined as T);
  return response.json();
}

/**
 * GET-Request mit JSON-Antwort.
 */
export type Parameter = Record<string, string | number | boolean | null | undefined>;

/** `optionen` gehen an fetch, etwa ein Signal zum Abbrechen */
export async function get<T = any>(path: string, params?: Parameter, optionen: RequestInit = {}): Promise<T> {
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
  const response = await anfrage(path, optionen);
  return inhalt(response);
}

/**
 * POST-Request mit JSON-Body.
 */
export async function post<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await anfrage(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return inhalt(response);
}

/**
 * PATCH-Request mit JSON-Body.
 */
export async function patch<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await anfrage(path, {
    method: "PATCH",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return inhalt(response);
}

/**
 * PUT-Request mit JSON-Body: ersetzt einen Wert ganz.
 */
export async function put<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await anfrage(path, {
    method: "PUT",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return inhalt(response);
}

/**
 * DELETE-Request, mit Angaben, wo der Weg sie braucht (etwa welche Freigaben zurückgehen).
 */
export async function del<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await anfrage(path, { method: "DELETE", body: body !== undefined ? JSON.stringify(body) : undefined });
  return inhalt(response);
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
