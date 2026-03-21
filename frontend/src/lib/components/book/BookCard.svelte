<script>
  import RatingStars from "../ui/RatingStars.svelte";
  import { coverUrl } from "../../api/books.js";
  import { toggleFavorit } from "../../api/user-data.js";
  import { navigate } from "../../router.svelte.js";
  import { selectionStore } from "../../stores/selection.svelte.js";

  let { book } = $props();

  let isSelected = $derived(selectionStore.has(book.id));

  // svelte-ignore state_referenced_locally
  let isFavorite = $state(book.is_favorite);
  let coverError = $state(false);

  function parseProgress(position, pageCount) {
    if (!position) return 0;
    try {
      if (position.startsWith("pdf:")) {
        const data = JSON.parse(position.slice(4));
        if (data.page && pageCount > 0) {
          return Math.round((data.page / pageCount) * 100);
        }
      }
      if (position.startsWith("epub:")) {
        const data = JSON.parse(position.slice(5));
        if (data.percent > 0) return data.percent;
      }
      if (position.startsWith("page:")) {
        return Math.min(Number(position.slice(5)) || 0, 100);
      }
      if (position.startsWith("percent:")) {
        return Number(position.slice(8)) || 0;
      }
    } catch { /* */ }
    return 0;
  }

  let progress = $derived(parseProgress(book.reading_position, book.page_count));

  const formatIcons = {
    pdf: "fa-file-pdf",
    epub: "fa-book-open",
    mobi: "fa-tablet-screen-button",
    txt: "fa-file-lines",
    md: "fa-file-code",
  };

  const formatLabels = {
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
      isFavorite = result.ist_favorit ?? result.is_favorite;
    } catch {
      // still
    }
  }

  function formatSize(bytes) {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  function formatPages(count) {
    if (!count) return "";
    return count + " Seiten";
  }
</script>

<a href="/book/{book.id}" class="book-card" class:selected={isSelected}
  onclick={(e) => {
    if (selectionStore.editMode || e.ctrlKey || e.metaKey) {
      e.preventDefault();
      selectionStore.toggle(book.id);
    }
  }}
  data-book-id={book.id}
>
  <div class="cover-container">
    <!-- Selektions-Checkbox -->
    <button
      class="select-checkbox"
      class:visible={isSelected || selectionStore.editMode}
      onclick={(e) => { e.preventDefault(); e.stopPropagation(); selectionStore.toggle(book.id); }}
    >
      {#if isSelected}
        <i class="fa-solid fa-square-check"></i>
      {:else}
        <i class="fa-regular fa-square"></i>
      {/if}
    </button>
    {#if !coverError}
      <img
        src={coverUrl(book.id, book.updated_at)}
        alt=""
        class="cover-image"
        loading="lazy"
        onerror={() => (coverError = true)}
      />
    {:else}
      <div class="cover-placeholder">
        <i class="fa-solid {formatIcons[book.file_format] || 'fa-file'} placeholder-icon"></i>
        <span class="placeholder-title">{book.title}</span>
        {#if book.author}
          <span class="placeholder-author">{book.author}</span>
        {/if}
      </div>
    {/if}

    <!-- Overlay-Aktionen (Hover) -->
    <div class="cover-overlay">
      <button
        class="overlay-btn favorite-btn"
        class:active={isFavorite}
        onclick={onFavoritClick}
        title={isFavorite ? "Aus Favoriten entfernen" : "Zu Favoriten"}
      >
        <i class="{isFavorite ? 'fa-solid' : 'fa-regular'} fa-heart"></i>
      </button>
      <button
        class="overlay-btn read-btn"
        title="Lesen"
        onclick={(e) => { e.preventDefault(); e.stopPropagation(); navigate(`/book/${book.id}/read`); }}
      >
        <i class="fa-solid fa-book-open-reader"></i>
      </button>
    </div>

    <!-- Badges -->
    <div class="badge-row">
      {#if book.file_format}
        <span class="format-badge">
          <i class="fa-solid {formatIcons[book.file_format] || 'fa-file'}"></i>
          {formatLabels[book.file_format] || book.file_format}
        </span>
      {/if}
      {#if book.is_to_read}
        <span class="status-badge to-read">
          <i class="fa-solid fa-bookmark"></i>
        </span>
      {/if}
    </div>

    {#if isFavorite}
      <span class="favorite-indicator">
        <i class="fa-solid fa-heart"></i>
      </span>
    {/if}

    <!-- Bewertung auf Cover -->
    {#if book.rating > 0}
      <div class="cover-rating">
        <RatingStars rating={book.rating} size="small" />
      </div>
    {/if}

    <!-- Lesefortschritt -->
    {#if book.reading_position && progress > 0}
      <div class="progress-bar">
        <div class="progress-fill" style="width: {progress}%"></div>
      </div>
    {/if}
  </div>

  <div class="card-body">
    <h3 class="book-title" title={book.title}>{book.title}</h3>
    <p class="book-author" title={book.author || ""}>{book.author || "Unbekannter Autor"}</p>

    <div class="card-bottom">
      {#if book.categories && book.categories.length > 0}
        <div class="card-tags">
          {#each book.categories.slice(0, 2) as cat (cat.id)}
            <span class="card-chip">{cat.name}</span>
          {/each}
          {#if book.categories.length > 2}
            <span class="card-chip more">+{book.categories.length - 2}</span>
          {/if}
        </div>
      {/if}

      <div class="card-meta">
        <div class="meta-details">
          {#if book.year}
            <span class="meta-item" title="Erscheinungsjahr">
              <i class="fa-solid fa-calendar"></i> {book.year}
            </span>
          {/if}
          {#if book.page_count}
            <span class="meta-item" title="Seiten">
              <i class="fa-solid fa-file-lines"></i> {formatPages(book.page_count)}
            </span>
          {/if}
          {#if book.file_size}
            <span class="meta-item" title="Dateigröße">
              {formatSize(book.file_size)}
            </span>
          {/if}
        </div>
      </div>
      {#if book.isbn}
        <div class="card-isbn" title="ISBN: {book.isbn}">
          <i class="fa-solid fa-barcode"></i> {book.isbn}
        </div>
      {/if}
    </div>
  </div>
</a>

<style>
  .book-card {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    overflow: hidden;
    background-color: var(--color-bg-secondary);
    text-decoration: none;
    color: inherit;
    transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
  }

  .book-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    border-color: var(--color-accent);
  }

  .book-card.selected {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 2px var(--color-accent);
  }

  /* Selektions-Checkbox */
  .select-checkbox {
    position: absolute;
    top: 0.375rem;
    right: 0.375rem;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    border: none;
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    color: #fff;
    font-size: 1rem;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.12s;
  }

  .select-checkbox.visible,
  .book-card:hover .select-checkbox {
    opacity: 1;
  }

  .book-card.selected .select-checkbox {
    opacity: 1;
    color: var(--color-accent);
    background: rgba(255, 255, 255, 0.9);
  }

  /* Cover - A4-Proportionen (1:1.414) */
  .cover-container {
    position: relative;
    aspect-ratio: 1 / 1.414;
    background-color: var(--color-bg-tertiary);
    overflow: hidden;
  }

  .cover-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s ease;
  }

  .book-card:hover .cover-image {
    transform: scale(1.03);
  }

  /* Placeholder ohne Cover */
  .cover-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: 1.5rem 1rem;
    text-align: center;
    gap: 0.75rem;
    background: linear-gradient(135deg, var(--color-bg-tertiary), var(--color-bg-secondary));
  }

  .placeholder-icon {
    font-size: 2.5rem;
    color: var(--color-text-muted);
    opacity: 0.5;
  }

  .placeholder-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    line-height: 1.3;
  }

  .placeholder-author {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Hover-Overlay */
  .cover-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.6) 0%, transparent 50%);
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.75rem;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .book-card:hover .cover-overlay {
    opacity: 1;
  }

  .overlay-btn {
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1rem;
    color: #fff;
    text-decoration: none;
    transition: background 0.15s, transform 0.15s;
  }

  .overlay-btn:hover {
    background: rgba(255, 255, 255, 0.25);
    transform: scale(1.1);
  }

  .favorite-btn.active {
    color: var(--color-favorite);
    background: rgba(239, 68, 68, 0.2);
  }

  /* Badges */
  .badge-row {
    position: absolute;
    top: 0.5rem;
    left: 0.5rem;
    display: flex;
    gap: 0.25rem;
  }

  .format-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(4px);
    color: #fff;
    font-size: 0.625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    letter-spacing: 0.02em;
  }

  .format-badge i {
    font-size: 0.5625rem;
  }

  .status-badge {
    display: inline-flex;
    align-items: center;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(4px);
    color: #fff;
    font-size: 0.625rem;
    padding: 0.2rem 0.35rem;
    border-radius: 4px;
  }

  .status-badge.to-read {
    color: var(--color-accent);
  }

  .favorite-indicator {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    color: var(--color-favorite);
    font-size: 0.875rem;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
  }

  /* Bewertung auf Cover */
  .cover-rating {
    position: absolute;
    bottom: 0.375rem;
    right: 0.375rem;
    padding: 0;
    transition: opacity 0.2s ease;
  }

  .book-card:hover .cover-rating {
    opacity: 0;
  }

  /* Lesefortschritt */
  .progress-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: rgba(0, 0, 0, 0.3);
  }

  .progress-fill {
    height: 100%;
    background: var(--color-accent);
    border-radius: 0 2px 2px 0;
    transition: width 0.3s ease;
  }

  /* Body */
  .card-body {
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
  }

  .book-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.3;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .book-author {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-bottom {
    margin-top: auto;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .card-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    flex-wrap: nowrap;
    overflow: hidden;
  }

  .meta-details {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .meta-item {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    white-space: nowrap;
  }

  .meta-item i {
    font-size: 0.5625rem;
  }

  .card-isbn {
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    display: flex;
    align-items: center;
    gap: 0.2rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-isbn i {
    font-size: 0.5rem;
  }

  .card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin-top: 0.25rem;
  }

  .card-chip {
    font-size: 0.5625rem;
    padding: 0.125rem 0.375rem;
    border-radius: 999px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .card-chip.more {
    color: var(--color-accent);
    font-weight: 600;
  }
</style>
