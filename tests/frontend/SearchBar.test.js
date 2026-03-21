/**
 * Tests fuer SearchBar-Komponente
 */
import { render, screen, fireEvent } from "@testing-library/svelte";
import SearchBar from "../src/lib/components/search/SearchBar.svelte";

// Mock fuer svelte-spa-router
const pushMock = vi.fn();
vi.mock("svelte-spa-router", () => ({
  push: (...args) => pushMock(...args),
}));

// Mock fuer Such-API
const vorschlaegeMock = vi.fn(() =>
  Promise.resolve({ suggestions: [] }),
);
vi.mock("../src/lib/api/search.js", () => ({
  vorschlaege: (...args) => vorschlaegeMock(...args),
}));

describe("SearchBar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    pushMock.mockClear();
    vorschlaegeMock.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("rendert das Suchfeld mit Platzhalter", () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    expect(input).toBeTruthy();
    expect(input.type).toBe("search");
  });

  it("ruft Vorschlaege erst nach Debounce-Verzoegerung ab", async () => {
    vorschlaegeMock.mockResolvedValue({ suggestions: ["Svelte Handbuch"] });
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");

    // Eingabe simulieren
    await fireEvent.input(input, { target: { value: "Svelte" } });

    // Vor Ablauf des Debounce: kein API-Aufruf
    expect(vorschlaegeMock).not.toHaveBeenCalled();

    // Debounce ablaufen lassen (300ms)
    await vi.advanceTimersByTimeAsync(300);

    expect(vorschlaegeMock).toHaveBeenCalledWith("Svelte");
  });

  it("ruft keine Vorschlaege bei weniger als 2 Zeichen ab", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.input(input, { target: { value: "a" } });

    await vi.advanceTimersByTimeAsync(300);

    expect(vorschlaegeMock).not.toHaveBeenCalled();
  });

  it("navigiert bei Enter-Taste zur Suchergebnisseite", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Hesse" } });
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(pushMock).toHaveBeenCalledWith("/search?q=Hesse");
  });

  it("navigiert nicht bei leerem Suchfeld und Enter", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(pushMock).not.toHaveBeenCalled();
  });

  it("navigiert nicht bei nur Leerzeichen und Enter", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.input(input, { target: { value: "   " } });
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(pushMock).not.toHaveBeenCalled();
  });

  it("kodiert Sonderzeichen in der Such-URL", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.input(input, { target: { value: "B\u00fccher & mehr" } });
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(pushMock).toHaveBeenCalledWith(
      `/search?q=${encodeURIComponent("B\u00fccher & mehr")}`,
    );
  });

  it("zeigt Vorschlaege als Dropdown an", async () => {
    vorschlaegeMock.mockResolvedValue({
      suggestions: ["Der Steppenwolf", "Der Prozess"],
    });
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Der" } });

    await vi.advanceTimersByTimeAsync(300);
    // Warten auf Promise-Aufloesung
    await vi.runAllTimersAsync();

    expect(screen.getByText("Der Steppenwolf")).toBeTruthy();
    expect(screen.getByText("Der Prozess")).toBeTruthy();
  });

  it("schliesst Dropdown bei Escape-Taste", async () => {
    vorschlaegeMock.mockResolvedValue({
      suggestions: ["Vorschlag"],
    });
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Vor" } });
    await vi.advanceTimersByTimeAsync(300);
    await vi.runAllTimersAsync();

    // Vorschlag sollte sichtbar sein
    expect(screen.getByText("Vorschlag")).toBeTruthy();

    // Escape druecken
    await fireEvent.keyDown(input, { key: "Escape" });

    // Vorschlag sollte nicht mehr sichtbar sein
    expect(screen.queryByText("Vorschlag")).toBeFalsy();
  });

  it("behandelt API-Fehler bei Vorschlaegen ohne Absturz", async () => {
    vorschlaegeMock.mockRejectedValue(new Error("Netzwerkfehler"));
    render(SearchBar);

    const input = screen.getByPlaceholderText("B\u00fccher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Test" } });

    await vi.advanceTimersByTimeAsync(300);
    await vi.runAllTimersAsync();

    // Kein Dropdown sichtbar, kein Fehler geworfen
    expect(screen.queryByRole("list")).toBeFalsy();
  });
});
