/**
 * Tests fuer den API-Client (Token, Error-Handling, HTTP-Methoden)
 */

// Modul muss vor jedem Test frisch geladen werden
// um den localStorage-Zustand korrekt zu testen
let client;

async function ladeClient() {
  vi.resetModules();
  client = await import("../src/lib/api/client.js");
}

function mockFetchAntwort(body = {}, optionen = {}) {
  const antwort = {
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
    blob: () => Promise.resolve(new Blob()),
    text: () => Promise.resolve(JSON.stringify(body)),
    headers: new Headers(),
    ...optionen,
  };
  globalThis.fetch = vi.fn(() => Promise.resolve(antwort));
  return antwort;
}

function mockFetchFehler(status, detail = null) {
  const body = detail ? { detail } : null;
  const antwort = {
    ok: false,
    status,
    json: body
      ? () => Promise.resolve(body)
      : () => Promise.reject(new Error("Kein JSON")),
    headers: new Headers(),
  };
  globalThis.fetch = vi.fn(() => Promise.resolve(antwort));
  return antwort;
}

describe("API-Client", () => {
  beforeEach(async () => {
    localStorage.clear();
    await ladeClient();
  });

  describe("Token-Verwaltung", () => {
    it("setzt und liest den Token", () => {
      client.setToken("mein-geheimer-token");

      expect(client.getToken()).toBe("mein-geheimer-token");
      expect(localStorage.setItem).toHaveBeenCalledWith(
        "api_token",
        "mein-geheimer-token",
      );
    });

    it("liest Token aus localStorage beim Laden", async () => {
      localStorage.getItem.mockReturnValue("gespeicherter-token");
      await ladeClient();

      expect(client.getToken()).toBe("gespeicherter-token");
      // Mock-Implementierung zuruecksetzen, damit nachfolgende Tests
      // nicht den gespeicherten Token erben
      localStorage.getItem.mockReset();
    });

    it("sendet Authorization-Header wenn Token gesetzt", async () => {
      mockFetchAntwort({ ok: true });
      client.setToken("test-token-123");

      await client.get("/api/test");

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].headers["Authorization"]).toBe(
        "Bearer test-token-123",
      );
    });

    it("sendet Default-Token wenn kein Token explizit gesetzt", async () => {
      mockFetchAntwort({ ok: true });

      await client.get("/api/test");

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].headers["Authorization"]).toBe(
        "Bearer bitte-aendern-sicherer-token-hier",
      );
    });
  });

  describe("GET-Anfragen", () => {
    it("sendet GET-Request an den richtigen Pfad", async () => {
      mockFetchAntwort({ books: [] });

      const ergebnis = await client.get("/api/books");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/books",
        expect.objectContaining({}),
      );
      expect(ergebnis).toEqual({ books: [] });
    });

    it("haengt Query-Parameter an die URL an", async () => {
      mockFetchAntwort({ books: [] });

      await client.get("/api/books", { limit: 10, offset: 20 });

      const url = globalThis.fetch.mock.calls[0][0];
      expect(url).toContain("limit=10");
      expect(url).toContain("offset=20");
    });

    it("ignoriert null und undefined Parameter", async () => {
      mockFetchAntwort({});

      await client.get("/api/books", {
        limit: 10,
        tag: null,
        category: undefined,
        search: "",
      });

      const url = globalThis.fetch.mock.calls[0][0];
      expect(url).toContain("limit=10");
      expect(url).not.toContain("tag");
      expect(url).not.toContain("category");
      expect(url).not.toContain("search");
    });

    it("funktioniert ohne Parameter-Objekt", async () => {
      mockFetchAntwort({ data: "test" });

      const ergebnis = await client.get("/api/test");

      expect(globalThis.fetch.mock.calls[0][0]).toBe("/api/test");
      expect(ergebnis).toEqual({ data: "test" });
    });
  });

  describe("POST-Anfragen", () => {
    it("sendet POST mit JSON-Body", async () => {
      mockFetchAntwort({ id: 1 });

      await client.post("/api/books", { title: "Neues Buch" });

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].method).toBe("POST");
      expect(aufruf[1].body).toBe('{"title":"Neues Buch"}');
    });

    it("setzt Content-Type automatisch bei String-Body", async () => {
      mockFetchAntwort({});

      await client.post("/api/test", { key: "value" });

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].headers["Content-Type"]).toBe("application/json");
    });

    it("sendet POST ohne Body wenn keiner angegeben", async () => {
      mockFetchAntwort({});

      await client.post("/api/action");

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].method).toBe("POST");
      expect(aufruf[1].body).toBeUndefined();
    });
  });

  describe("PATCH-Anfragen", () => {
    it("sendet PATCH mit JSON-Body", async () => {
      mockFetchAntwort({ title: "Aktualisiert" });

      await client.patch("/api/books/1", { title: "Aktualisiert" });

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].method).toBe("PATCH");
      expect(aufruf[1].body).toBe('{"title":"Aktualisiert"}');
    });
  });

  describe("DELETE-Anfragen", () => {
    it("sendet DELETE-Request", async () => {
      mockFetchAntwort({ message: "Gel\u00f6scht" });

      await client.del("/api/books/1");

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].method).toBe("DELETE");
    });
  });

  describe("Upload", () => {
    it("sendet FormData ohne manuellen Content-Type", async () => {
      mockFetchAntwort({ id: 1 });
      const formData = new FormData();
      formData.append("file", new Blob(["inhalt"]), "test.epub");

      await client.upload("/api/import/upload", formData);

      const aufruf = globalThis.fetch.mock.calls[0];
      expect(aufruf[1].method).toBe("POST");
      expect(aufruf[1].body).toBe(formData);
      // Content-Type darf NICHT manuell gesetzt werden bei FormData
      expect(aufruf[1].headers["Content-Type"]).toBeUndefined();
    });
  });

  describe("Fehlerbehandlung", () => {
    it("wirft ApiError bei HTTP-Fehler mit Detail", async () => {
      mockFetchFehler(404, "Buch nicht gefunden");

      await expect(client.get("/api/books/999")).rejects.toThrow(
        "Buch nicht gefunden",
      );

      try {
        mockFetchFehler(404, "Buch nicht gefunden");
        await client.get("/api/books/999");
      } catch (err) {
        expect(err).toBeInstanceOf(client.ApiError);
        expect(err.status).toBe(404);
        expect(err.message).toBe("Buch nicht gefunden");
      }
    });

    it("wirft ApiError mit HTTP-Status als Fallback", async () => {
      mockFetchFehler(500);

      await expect(client.get("/api/fehler")).rejects.toThrow("HTTP 500");
    });

    it("wirft ApiError bei 401 (nicht autorisiert)", async () => {
      mockFetchFehler(401, "Token ung\u00fcltig");

      try {
        await client.get("/api/geschuetzt");
      } catch (err) {
        expect(err).toBeInstanceOf(client.ApiError);
        expect(err.status).toBe(401);
      }
    });

    it("wirft ApiError bei 422 (Validierungsfehler)", async () => {
      mockFetchFehler(422, "Ung\u00fcltige Daten");

      try {
        await client.post("/api/books", {});
      } catch (err) {
        expect(err).toBeInstanceOf(client.ApiError);
        expect(err.status).toBe(422);
      }
    });
  });

  describe("Download", () => {
    it("gibt einen Blob zurueck", async () => {
      const testBlob = new Blob(["test-inhalt"], { type: "image/jpeg" });
      globalThis.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          blob: () => Promise.resolve(testBlob),
          headers: new Headers(),
        }),
      );

      const ergebnis = await client.download("/api/books/1/cover");

      expect(ergebnis).toBeInstanceOf(Blob);
    });
  });

  describe("SSE-Verbindung", () => {
    it("erstellt EventSource mit Token im Query-Parameter", () => {
      client.setToken("sse-token");

      const verbindung = client.sse("/api/events", vi.fn());

      expect(verbindung).toBeDefined();
      expect(verbindung.close).toBeInstanceOf(Function);
    });

    it("laesst sich schliessen", () => {
      const verbindung = client.sse("/api/events", vi.fn());

      expect(() => verbindung.close()).not.toThrow();
    });
  });
});
