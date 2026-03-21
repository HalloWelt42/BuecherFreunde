/**
 * Tests fuer BookCard-Komponente
 */
import { render, screen } from "@testing-library/svelte";
import BookCard from "../src/lib/components/book/BookCard.svelte";

// Mocks fuer API-Module
vi.mock("../src/lib/api/books.js", () => ({
  coverUrl: vi.fn((id) => `/api/books/${id}/cover`),
}));

vi.mock("../src/lib/api/user-data.js", () => ({
  toggleFavorit: vi.fn(() => Promise.resolve({ is_favorite: true })),
}));

function erstelleTestBuch(ueberschreibungen = {}) {
  return {
    id: 1,
    title: "Der Steppenwolf",
    author: "Hermann Hesse",
    file_format: "epub",
    file_size: 1536000,
    rating: 4,
    is_favorite: false,
    ...ueberschreibungen,
  };
}

describe("BookCard", () => {
  it("zeigt Buchtitel und Autor an", () => {
    const buch = erstelleTestBuch();
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("Der Steppenwolf")).toBeTruthy();
    expect(screen.getByText("Hermann Hesse")).toBeTruthy();
  });

  it("zeigt 'Unbekannt' wenn kein Autor vorhanden", () => {
    const buch = erstelleTestBuch({ author: null });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("Unbekannt")).toBeTruthy();
  });

  it("zeigt auch leeren Autor als 'Unbekannt' an", () => {
    const buch = erstelleTestBuch({ author: "" });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("Unbekannt")).toBeTruthy();
  });

  it("zeigt das Format-Badge an", () => {
    const buch = erstelleTestBuch({ file_format: "pdf" });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("PDF")).toBeTruthy();
  });

  it("zeigt die Dateigroesse korrekt formatiert an (MB)", () => {
    const buch = erstelleTestBuch({ file_size: 1536000 });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("1.5 MB")).toBeTruthy();
  });

  it("zeigt die Dateigroesse korrekt formatiert an (KB)", () => {
    const buch = erstelleTestBuch({ file_size: 512 * 1024 });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("512.0 KB")).toBeTruthy();
  });

  it("zeigt die Dateigroesse korrekt formatiert an (Bytes)", () => {
    const buch = erstelleTestBuch({ file_size: 500 });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("500 B")).toBeTruthy();
  });

  it("erzeugt einen Link zur Buchdetailseite", () => {
    const buch = erstelleTestBuch({ id: 42 });
    render(BookCard, { props: { book: buch } });

    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("#/book/42");
  });

  it("zeigt das Cover-Bild mit korrekter URL", () => {
    const buch = erstelleTestBuch({ id: 7 });
    render(BookCard, { props: { book: buch } });

    const img = screen.getByAltText("Cover: Der Steppenwolf");
    expect(img).toBeTruthy();
    expect(img.getAttribute("src")).toBe("/api/books/7/cover");
  });

  it("zeigt den Favoriten-Button mit leerem Herz", () => {
    const buch = erstelleTestBuch({ is_favorite: false });
    render(BookCard, { props: { book: buch } });

    const btn = screen.getByTitle("Zu Favoriten hinzuf\u00fcgen");
    expect(btn).toBeTruthy();
    expect(btn.textContent.trim()).toBe("\u2661");
  });

  it("zeigt den Favoriten-Button mit vollem Herz wenn favorisiert", () => {
    const buch = erstelleTestBuch({ is_favorite: true });
    render(BookCard, { props: { book: buch } });

    const btn = screen.getByTitle("Aus Favoriten entfernen");
    expect(btn).toBeTruthy();
    expect(btn.textContent.trim()).toBe("\u2764");
  });

  it("rendert Sterne fuer die Bewertung", () => {
    const buch = erstelleTestBuch({ rating: 3 });
    render(BookCard, { props: { book: buch } });

    // 3 gefuellte Sterne + 2 leere Sterne = 5 Stern-Buttons
    const sternButtons = screen.getAllByRole("button").filter(
      (btn) => btn.title && btn.title.includes("Stern"),
    );
    expect(sternButtons.length).toBe(5);
  });

  it("behandelt unbekannte Formate mit Format-Fallback", () => {
    const buch = erstelleTestBuch({ file_format: "xyz" });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("xyz")).toBeTruthy();
  });
});
