<script>
  import RatingStars from "../ui/RatingStars.svelte";
  import { coverUrl } from "../../api/books.js";
  import { toggleFavorit } from "../../api/user-data.js";

  let { book } = $props();

  let isFavorite = $state(book.is_favorite);
  let coverError = $state(false);

  const formatIcons = {
    pdf: "PDF",
    epub: "EPUB",
    mobi: "MOBI",
    txt: "TXT",
    md: "MD",
  };

  async function onFavoritClick(event) {
    event.preventDefault();
    event.stopPropagation();
    try {
      const result = await toggleFavorit(book.id);
      isFavorite = result.is_favorite;
    } catch {
      // Fehler still ignorieren
    }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }
</script>

<a href="#/book/{book.id}" class="book-card">
  <div class="cover-container">
    {#if !coverError}
      <img
        src={coverUrl(book.id)}
        alt="Cover: {book.title}"
        class="cover-image"
        loading="lazy"
        onerror={() => (coverError = true)}
      />
    {:else}
      <div class="cover-placeholder">
        <span class="placeholder-format">
          {formatIcons[book.file_format] || "?"}
        </span>
        <span class="placeholder-title">{book.title}</span>
      </div>
    {/if}

    <button
      class="favorite-btn"
      class:active={isFavorite}
      onclick={onFavoritClick}
      title={isFavorite ? "Aus Favoriten entfernen" : "Zu Favoriten hinzufügen"}
    >
      {isFavorite ? "\u2764" : "\u2661"}
    </button>

    {#if book.file_format}
      <span class="format-badge">
        {formatIcons[book.file_format] || book.file_format}
      </span>
    {/if}
  </div>

  <div class="card-body">
    <h3 class="book-title" title={book.title}>{book.title}</h3>
    <p class="book-author" title={book.author}>{book.author || "Unbekannt"}</p>

    <div class="card-footer">
      <RatingStars rating={book.rating} />
      <span class="book-size">{formatSize(book.file_size)}</span>
    </div>
  </div>
</a>

<style>
  .book-card {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
    background-color: var(--color-bg-secondary);
    text-decoration: none;
    color: inherit;
    transition: transform 0.15s, box-shadow 0.15s;
  }

  .book-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .cover-container {
    position: relative;
    aspect-ratio: 2 / 3;
    background-color: var(--color-bg-tertiary);
    overflow: hidden;
  }

  .cover-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .cover-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: 1rem;
    text-align: center;
    gap: 0.5rem;
  }

  .placeholder-format {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
  }

  .placeholder-title {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
  }

  .favorite-btn {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    background: rgba(0, 0, 0, 0.5);
    border: none;
    border-radius: 50%;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1rem;
    color: #fff;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .book-card:hover .favorite-btn {
    opacity: 1;
  }

  .favorite-btn.active {
    opacity: 1;
    color: var(--color-favorite);
  }

  .format-badge {
    position: absolute;
    bottom: 0.5rem;
    left: 0.5rem;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    font-size: 0.625rem;
    font-weight: 700;
    font-family: var(--font-mono);
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
  }

  .card-body {
    padding: 0.625rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .book-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .book-author {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0.25rem;
  }

  .book-size {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
</style>
