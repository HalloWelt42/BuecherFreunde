/**
 * API-Client mit Bearer Token Auth, Fehlerbehandlung und SSE-Support.
 */

const SCHLUESSEL = "api_token";

// Die Anmeldung liegt im Speicher des Browsers (je Adresse geteilt von allen Tabs) und wird bei jeder Anfrage frisch
// gelesen: meldet man sich in einem Tab an, gilt das sofort für alle (etwa einen Leser, der aus dem Assistenten an einer
// Seite geöffnet wurde und noch die Anmeldung zeigt).
let apiToken = lesen() ?? "";

/** @returns {string | null} null, wenn es keinen Speicher gibt (dann gilt der Wert dieser Seite) */
function lesen() {
  try {
    return localStorage.getItem(SCHLUESSEL) || "";
  } catch {
    return null;
  }
}

/** Callback wenn Token ungültig ist - wird von App.svelte gesetzt */
let onAuthRequired = null;

/**
 * Registriert einen Callback für fehlende/ungültige Authentifizierung.
 * @param {() => void} callback
 */
export function onAuthError(callback) {
  onAuthRequired = callback;
}

/**
 * Prüft ob ein Token gespeichert ist.
 * @returns {boolean}
 */
export function hasToken() {
  return getToken().length > 0;
}

/**
 * Ein anderer Tab hat sich an- oder abgemeldet.
 * @param {(token: string) => void} tun
 */
export function beiTokenWechsel(tun) {
  addEventListener("storage", (e) => {
    if (e.key === SCHLUESSEL) {
      apiToken = e.newValue || "";
      tun(apiToken);
    }
  });
}

/**
 * Setzt den API-Token für alle Requests.
 * @param {string} token
 */
export function setToken(token) {
  apiToken = token;
  if (token) localStorage.setItem(SCHLUESSEL, token);
  else localStorage.removeItem(SCHLUESSEL);
}

/**
 * Abmelden: beendet die Sitzung in der Kellerwolke (auf einem gekoppelten Gerät trennt es das Gerät).
 */
export async function abmelden() {
  try {
    await fetch("/api/anmeldung/abmelden", {
      method: "POST",
      headers: { "X-Kellerwolke-Sitzung": getToken() },
    });
  } catch {
    // egal: lokal ist man danach abgemeldet
  }
  setToken("");
  if (onAuthRequired) onAuthRequired();
}

/**
 * Gibt den aktuellen Token zurück.
 * @returns {string}
 */
export function getToken() {
  apiToken = lesen() ?? apiToken;
  return apiToken;
}

/**
 * API-Fehler mit Statuscode und Nachricht.
 */
export class ApiError extends Error {
  /**
   * @param {number} status
   * @param {string} message
   * @param {*} [data]
   */
  constructor(status, message, data) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Basis-Fetch mit Auth-Header und Fehlerbehandlung.
 * @param {string} path - API-Pfad (z.B. "/api/books")
 * @param {RequestInit} [options]
 * @returns {Promise<Response>}
 */
async function baseFetch(path, options = {}) {
  const headers = { ...options.headers };

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

  const response = await fetch(path, { ...options, headers });

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

    const message = data?.detail || `HTTP ${response.status}`;
    throw new ApiError(response.status, message, data);
  }

  return response;
}

/**
 * GET-Request mit JSON-Antwort.
 * @param {string} path
 * @param {Record<string, string|number|boolean|null|undefined>} [params]
 * @returns {Promise<*>}
 */
export async function get(path, params) {
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
  const response = await baseFetch(path);
  return response.json();
}

/**
 * POST-Request mit JSON-Body.
 * @param {string} path
 * @param {*} [body]
 * @returns {Promise<*>}
 */
export async function post(path, body) {
  const response = await baseFetch(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return response.json();
}

/**
 * PATCH-Request mit JSON-Body.
 * @param {string} path
 * @param {*} body
 * @returns {Promise<*>}
 */
export async function patch(path, body) {
  const response = await baseFetch(path, {
    method: "PATCH",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return response.json();
}

/**
 * DELETE-Request.
 * @param {string} path
 * @returns {Promise<*>}
 */
export async function del(path) {
  const response = await baseFetch(path, { method: "DELETE" });
  return response.json();
}

/**
 * Datei-Upload via FormData.
 * @param {string} path
 * @param {FormData} formData
 * @returns {Promise<*>}
 */
export async function upload(path, formData) {
  const response = await baseFetch(path, {
    method: "POST",
    body: formData,
    // Content-Type wird automatisch mit Boundary gesetzt
  });
  return response.json();
}

/**
 * SSE-Verbindung für Echtzeit-Events.
 * @param {string} path
 * @param {(event: {type: string, data: *}) => void} onEvent
 * @param {(error: Error) => void} [onError]
 * @returns {{ close: () => void }}
 */
export function sse(path, onEvent, onError) {
  const token = getToken();
  const url = token ? `${path}?token=${token}` : path;
  const source = new EventSource(url);

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onEvent({ type: "message", data });
    } catch {
      onEvent({ type: "message", data: event.data });
    }
  };

  source.onerror = (event) => {
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
 * @param {string} path
 * @returns {Promise<Blob>}
 */
export async function download(path) {
  const response = await baseFetch(path);
  return response.blob();
}
