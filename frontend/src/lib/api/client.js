/**
 * API-Client mit Bearer Token Auth, Fehlerbehandlung und SSE-Support.
 */

let apiToken = localStorage.getItem("api_token") || "";

/**
 * Setzt den API-Token für alle Requests.
 * @param {string} token
 */
export function setToken(token) {
  apiToken = token;
  localStorage.setItem("api_token", token);
}

/**
 * Gibt den aktuellen Token zurück.
 * @returns {string}
 */
export function getToken() {
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

  if (apiToken) {
    headers["Authorization"] = `Bearer ${apiToken}`;
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
    body: JSON.stringify(body),
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
  const url = apiToken ? `${path}?token=${apiToken}` : path;
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
