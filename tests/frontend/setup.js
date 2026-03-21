/**
 * Vitest Setup - jsdom Umgebung, globale Mocks
 *
 * HINWEIS: Die tatsaechlich verwendete Setup-Datei liegt unter
 * frontend/vitest.setup.js (wegen node_modules-Aufloesung).
 * Diese Datei wird als Referenz gepflegt.
 */
// vi ist global verfuegbar (globals: true in vitest.config)

// localStorage Mock
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] ?? null),
    setItem: vi.fn((key, value) => {
      store[key] = String(value);
    }),
    removeItem: vi.fn((key) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index) => Object.keys(store)[index] ?? null),
  };
})();

Object.defineProperty(globalThis, "localStorage", {
  value: localStorageMock,
  writable: true,
});

// fetch Mock - standardmaessig leere erfolgreiche Antwort
globalThis.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    blob: () => Promise.resolve(new Blob()),
    text: () => Promise.resolve(""),
    headers: new Headers(),
  }),
);

// EventSource Mock fuer SSE-Tests
class MockEventSource {
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.onmessage = null;
    this.onerror = null;
    this.onopen = null;
  }
  close() {
    this.readyState = 2;
  }
}

globalThis.EventSource = MockEventSource;

// Vor jedem Test Mocks zuruecksetzen
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});
