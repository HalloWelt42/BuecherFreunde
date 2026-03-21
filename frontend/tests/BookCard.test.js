/**
 * Tests für BookCard-Komponente
 */
import { render, screen } from "@testing-library/svelte";
import BookCard from "../src/lib/components/book/BookCard.svelte";

// Mocks für API-Module
vi.mock("../src/lib/api/books.js", () => ({
  coverUrl: vi.fn((id) => `/api/books/${id}/cover`),
}));

vi.mock("../src/lib/api/user-data.js", () => ({
  toggleFavorit: vi.fn(() => Promise.resolve({ ist_favorit: true })),
}));

vi.mock("../src/lib/router.svelte.js", () => ({
  navigate: vi.fn(),
  route: { path: "/", qs: "", params: {} },
}));

function erstelleTestBuch(ueberschreibungen = {}) {
  return {
    id: 1,
    title: "Der Steppenwolf",
    author: "Hermann Hesse",
    file_format: "epub",
    file_size: 1536000,
    page_count: 250,
    rating: 4,
    is_favorite: false,
    is_to_read: false,
    categories: [],
    tags: [],
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

  it("zeigt 'Unbekannter Autor' wenn kein Autor vorhanden", () => {
    const buch = erstelleTestBuch({ author: null });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("Unbekannter Autor")).toBeTruthy();
  });

  it("zeigt auch leeren Autor als 'Unbekannter Autor' an", () => {
    const buch = erstelleTestBuch({ author: "" });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("Unbekannter Autor")).toBeTruthy();
  });

  it("zeigt das Format-Badge an", () => {
    const buch = erstelleTestBuch({ file_format: "pdf" });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("PDF")).toBeTruthy();
  });

  it("zeigt die Dateigröße korrekt formatiert an (MB)", () => {
    const buch = erstelleTestBuch({ file_size: 1536000 });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("1.5 MB")).toBeTruthy();
  });

  it("zeigt die Dateigröße korrekt formatiert an (KB)", () => {
    const buch = erstelleTestBuch({ file_size: 512 * 1024 });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("512 KB")).toBeTruthy();
  });

  it("zeigt die Dateigröße korrekt formatiert an (Bytes)", () => {
    const buch = erstelleTestBuch({ file_size: 500 });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("500 B")).toBeTruthy();
  });

  it("erzeugt einen Link zur Buchdetailseite", () => {
    const buch = erstelleTestBuch({ id: 42 });
    render(BookCard, { props: { book: buch } });

    const links = screen.getAllByRole("link");
    const bookLink = links.find((l) => l.getAttribute("href") === "/book/42");
    expect(bookLink).toBeTruthy();
  });

  it("zeigt den Favorit-Button", () => {
    const buch = erstelleTestBuch({ is_favorite: false });
    render(BookCard, { props: { book: buch } });

    const btn = screen.getByTitle("Zu Favoriten");
    expect(btn).toBeTruthy();
  });

  it("zeigt den Favorit-Button als aktiv wenn favorisiert", () => {
    const buch = erstelleTestBuch({ is_favorite: true });
    render(BookCard, { props: { book: buch } });

    const btn = screen.getByTitle("Aus Favoriten entfernen");
    expect(btn).toBeTruthy();
  });

  it("zeigt Seitenanzahl an", () => {
    const buch = erstelleTestBuch({ page_count: 250 });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("250 S.")).toBeTruthy();
  });

  it("zeigt Kategorien als Chips an", () => {
    const buch = erstelleTestBuch({
      categories: [
        { id: 1, name: "Belletristik" },
        { id: 2, name: "Klassiker" },
      ],
    });
    render(BookCard, { props: { book: buch } });

    expect(screen.getByText("Belletristik")).toBeTruthy();
    expect(screen.getByText("Klassiker")).toBeTruthy();
  });
});
