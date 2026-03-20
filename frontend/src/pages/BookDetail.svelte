<script>
  import { holeBuch, coverUrl } from "../lib/api/books.js";
  import { toggleFavorit, toggleZumLesen, setzeBewertung } from "../lib/api/user-data.js";
  import RatingStars from "../lib/components/ui/RatingStars.svelte";
  import BookMeta from "../lib/components/book/BookMeta.svelte";

  let { params } = $props();

  let book = $state(null);
  let laden = $state(true);
  let fehler = $state(null);
  let coverError = $state(false);

  $effect(() => {
    ladeBuch(Number(params.id));
  });

  async function ladeBuch(id) {
    laden = true;
    fehler = null;
    try {
      book = await holeBuch(id);
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  async function onFavoritToggle() {
    if (!book) return;
    try {
      const result = await toggleFavorit(book.id);
      book = { ...book, is_favorite: result.is_favorite };
    } catch { /* still */ }
  }

  async function onZumLesenToggle() {
    if (!book) return;
    try {
      const result = await toggleZumLesen(book.id);
      book = { ...book, is_to_read: result.is_to_read };
    } catch { /* still */ }
  }

  async function onRate(rating) {
    if (!book) return;
    try {
      const result = await setzeBewertung(book.id, rating);
      book = { ...book, rating: result.rating };
    } catch { /* still */ }
  }
</script>

<div class="book-detail">
  <div class="page-header">
    <a href="#/" class="back-link">&larr; Bibliothek</a>
  </div>

  {#if laden}
    <p class="status-text">Buch wird geladen...</p>
  {:else if fehler}
    <p class="status-text error">Fehler: {fehler}</p>
  {:else if book}
    <div class="detail-layout">
      <div class="cover-section">
        {#if !coverError}
          <img
            src={coverUrl(book.id)}
            alt="Cover: {book.title}"
            class="cover-image"
            onerror={() => (coverError = true)}
          />
        {:else}
          <div class="cover-placeholder">
            <span>{(book.file_format || "?").toUpperCase()}</span>
          </div>
        {/if}

        <div class="cover-actions">
          <a href="#/book/{book.id}/read" class="btn btn-primary">
            Lesen
          </a>
          <a
            href="/api/books/{book.id}/file"
            download
            class="btn btn-secondary"
          >
            Herunterladen
          </a>
        </div>
      </div>

      <div class="info-section">
        <h1 class="book-title">{book.title}</h1>
        <p class="book-author">{book.author || "Unbekannter Autor"}</p>

        <div class="rating-row">
          <RatingStars rating={book.rating} interactive onRate={onRate} />
        </div>

        <div class="action-row">
          <button
            class="action-btn"
            class:active={book.is_favorite}
            onclick={onFavoritToggle}
          >
            {book.is_favorite ? "\u2764 Favorit" : "\u2661 Favorit"}
          </button>
          <button
            class="action-btn"
            class:active={book.is_to_read}
            onclick={onZumLesenToggle}
          >
            {book.is_to_read ? "\u2713 Leseliste" : "+ Leseliste"}
          </button>
        </div>

        <div class="meta-section">
          <h2 class="section-title">Details</h2>
          <BookMeta {book} />
        </div>

        {#if book.categories && book.categories.length > 0}
          <div class="tags-section">
            <h2 class="section-title">Kategorien</h2>
            <div class="chip-list">
              {#each book.categories as cat (cat.id)}
                <a href="#/?category={cat.id}" class="chip">{cat.name}</a>
              {/each}
            </div>
          </div>
        {/if}

        {#if book.tags && book.tags.length > 0}
          <div class="tags-section">
            <h2 class="section-title">Tags</h2>
            <div class="chip-list">
              {#each book.tags as tag (tag.id)}
                <a
                  href="#/?tag={tag.id}"
                  class="chip tag-chip"
                  style="--tag-color: {tag.color || 'var(--color-accent)'}"
                >
                  {tag.name}
                </a>
              {/each}
            </div>
          </div>
        {/if}

        {#if book.reading_position}
          <div class="position-section">
            <h2 class="section-title">Lesefortschritt</h2>
            <p class="position-info">Position: {book.reading_position}</p>
            <a href="#/book/{book.id}/read" class="btn btn-secondary btn-sm">
              Weiterlesen
            </a>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .book-detail {
    max-width: 960px;
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .back-link {
    color: var(--color-accent);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .status-text {
    color: var(--color-text-muted);
    padding: 2rem 0;
  }

  .status-text.error {
    color: var(--color-error);
  }

  .detail-layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: 2rem;
  }

  @media (max-width: 640px) {
    .detail-layout {
      grid-template-columns: 1fr;
    }
  }

  .cover-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .cover-image {
    width: 100%;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .cover-placeholder {
    aspect-ratio: 2 / 3;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--color-bg-tertiary);
    border-radius: 8px;
    font-size: 2rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }

  .cover-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.625rem 1rem;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    border: none;
    transition: opacity 0.15s;
  }

  .btn:hover {
    opacity: 0.9;
  }

  .btn-primary {
    background-color: var(--color-accent);
    color: #fff;
  }

  .btn-secondary {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
  }

  .btn-sm {
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
  }

  .info-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .book-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
  }

  .book-author {
    font-size: 1.125rem;
    color: var(--color-text-secondary);
  }

  .rating-row {
    font-size: 1.25rem;
  }

  .action-row {
    display: flex;
    gap: 0.5rem;
  }

  .action-btn {
    padding: 0.375rem 0.875rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .action-btn:hover {
    background-color: var(--color-bg-tertiary);
  }

  .action-btn.active {
    border-color: var(--color-accent);
    color: var(--color-accent);
    background-color: var(--color-accent-light);
  }

  .section-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.375rem;
  }

  .meta-section {
    padding-top: 0.5rem;
  }

  .tags-section {
    padding-top: 0.25rem;
  }

  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .chip {
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    text-decoration: none;
  }

  .chip:hover {
    background-color: var(--color-bg-tertiary);
  }

  .tag-chip {
    background-color: color-mix(in srgb, var(--tag-color) 15%, transparent);
    color: var(--tag-color);
    border-color: color-mix(in srgb, var(--tag-color) 30%, transparent);
  }

  .position-section {
    padding-top: 0.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .position-info {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }
</style>
