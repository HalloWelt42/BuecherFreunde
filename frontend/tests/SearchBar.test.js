/**
 * Tests für SearchBar-Komponente
 */
import { render, screen, fireEvent } from "@testing-library/svelte";
import SearchBar from "../src/lib/components/search/SearchBar.svelte";

// Mock für Router
const navigateMock = vi.fn();
vi.mock("../src/lib/router.svelte.js", () => ({
  navigate: (...args) => navigateMock(...args),
  route: { path: "/", qs: "", params: {} },
}));

// Mock für Such-API
const vorschlaegeMock = vi.fn(() =>
  Promise.resolve({ vorschlaege: [] }),
);
vi.mock("../src/lib/api/search.js", () => ({
  vorschlaege: (...args) => vorschlaegeMock(...args),
}));

describe("SearchBar", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    navigateMock.mockClear();
    vorschlaegeMock.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("rendert das Suchfeld mit Platzhalter", () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    expect(input).toBeTruthy();
    expect(input.type).toBe("search");
  });

  it("ruft Vorschläge erst nach Debounce-Verzögerung ab", async () => {
    vorschlaegeMock.mockResolvedValue({ vorschlaege: [{ id: 1, titel: "Svelte Handbuch", autor: "Autor", typ: "titel" }] });
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");

    await fireEvent.input(input, { target: { value: "Svelte" } });

    expect(vorschlaegeMock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(300);

    expect(vorschlaegeMock).toHaveBeenCalledWith("Svelte");
  });

  it("ruft keine Vorschläge bei weniger als 2 Zeichen ab", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.input(input, { target: { value: "a" } });

    await vi.advanceTimersByTimeAsync(300);

    expect(vorschlaegeMock).not.toHaveBeenCalled();
  });

  it("navigiert bei Enter-Taste zur Suchergebnisseite", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Hesse" } });
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(navigateMock).toHaveBeenCalledWith("/search?q=Hesse");
  });

  it("navigiert nicht bei leerem Suchfeld und Enter", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("navigiert nicht bei nur Leerzeichen und Enter", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.input(input, { target: { value: "   " } });
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("kodiert Sonderzeichen in der Such-URL", async () => {
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Bücher & mehr" } });
    await fireEvent.keyDown(input, { key: "Enter" });

    expect(navigateMock).toHaveBeenCalledWith(
      `/search?q=${encodeURIComponent("Bücher & mehr")}`,
    );
  });

  it("zeigt Vorschläge als Dropdown an", async () => {
    vorschlaegeMock.mockResolvedValue({
      vorschlaege: [
        { id: 1, titel: "Der Steppenwolf", autor: "Hesse", typ: "titel" },
        { id: 2, titel: "Der Prozess", autor: "Kafka", typ: "titel" },
      ],
    });
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Der" } });

    await vi.advanceTimersByTimeAsync(300);
    await vi.runAllTimersAsync();

    expect(screen.getByText("Der Steppenwolf")).toBeTruthy();
    expect(screen.getByText("Der Prozess")).toBeTruthy();
  });

  it("schließt Dropdown bei Escape-Taste", async () => {
    vorschlaegeMock.mockResolvedValue({
      vorschlaege: [
        { id: 1, titel: "Vorschlag", autor: "", typ: "titel" },
      ],
    });
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Vor" } });
    await vi.advanceTimersByTimeAsync(300);
    await vi.runAllTimersAsync();

    expect(screen.getByText("Vorschlag")).toBeTruthy();

    await fireEvent.keyDown(input, { key: "Escape" });

    expect(screen.queryByText("Vorschlag")).toBeFalsy();
  });

  it("behandelt API-Fehler bei Vorschlägen ohne Absturz", async () => {
    vorschlaegeMock.mockRejectedValue(new Error("Netzwerkfehler"));
    render(SearchBar);

    const input = screen.getByPlaceholderText("Bücher durchsuchen...");
    await fireEvent.input(input, { target: { value: "Test" } });

    await vi.advanceTimersByTimeAsync(300);
    await vi.runAllTimersAsync();

    expect(screen.queryByRole("list")).toBeFalsy();
  });
});
