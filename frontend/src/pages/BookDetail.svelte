<script>
  import { holeBuch, coverUrl } from "../lib/api/books.js";
  import { toggleFavorit, toggleZumLesen, setzeBewertung } from "../lib/api/user-data.js";
  import RatingStars from "../lib/components/ui/RatingStars.svelte";
  import BookMeta from "../lib/components/book/BookMeta.svelte";
  import AiCategorizeDialog from "../lib/components/book/AiCategorizeDialog.svelte";
  import NoteList from "../lib/components/notes/NoteList.svelte";

  let { params } = $props();

  let book = $state(null);
  let laden = $state(true);
  let fehler = $state(null);
  let coverError = $state(false);
  let aiDialogOpen = $state(false);

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
      book = { ...book, is_favorite: result.ist_favorit ?? result.is_favorite };
    } catch { /* still */ }
  }

  async function onZumLesenToggle() {
    if (!book) return;
    try {
      const result = await toggleZumLesen(book.id);
      book = { ...book, is_to_read: result.zu_lesen ?? result.is_to_read };
    } catch { /* still */ }
  }

  async function onRate(rating) {
    if (!book) return;
    try {
      const result = await setzeBewertung(book.id, rating);
      book = { ...book, rating: result.bewertung ?? result.rating };
    } catch { /* still */ }
  }

  const papierLabel = { normal: "Normal", sepia: "Sepia", dunkel: "Dunkel" };
  const ansichtLabel = { breite: "Seitenbreite", seite: "Ganze Seite" };

  function parseLeseposition(pos, format) {
    if (!pos) return { items: [], fontPreview: null };
    const items = [];
    let fontPreview = null;

    if (pos.startsWith("pdf:")) {
      try {
        const d = JSON.parse(pos.slice(4));
        if (d.page) items.push({ label: "Seite", value: d.page });
        if (d.zoom) items.push({ label: "Zoom", value: `${d.zoom}%` });
        if (d.ansicht) items.push({ label: "Ansicht", value: d.ansicht, type: "pdf-ansicht" });
        if (d.papier) items.push({ label: "Papier", value: d.papier, type: "papier" });
      } catch { items.push({ label: "Position", value: pos }); }
    } else if (pos.startsWith("epub:")) {
      try {
        const d = JSON.parse(pos.slice(5));
        if (d.fontSize) items.push({ label: "Schrift", value: `${d.fontSize}%` });
        if (d.fontFamily) {
          fontPreview = {
            family: d.fontFamily,
            name: d.fontFamily.split(",")[0].trim(),
            fg: d.fgColor || null,
            bg: d.bgColor || null,
          };
        }
        if (d.lineHeight) items.push({ label: "Zeilenabstand", value: `${d.lineHeight}` });
        if (d.singlePage != null) items.push({ label: "Layout", value: d.singlePage ? "single" : "double", type: "layout" });
        if (d.maxWidthSingle) items.push({ label: "Breite (1-seitig)", value: `${d.maxWidthSingle}px` });
        if (d.maxWidthDouble) items.push({ label: "Breite (2-seitig)", value: `${d.maxWidthDouble}px` });
      } catch { items.push({ label: "Position", value: pos }); }
    } else if (pos.startsWith("txt:")) {
      const rest = pos.slice(4);
      if (rest.startsWith("{")) {
        try {
          const d = JSON.parse(rest);
          if (d.scrollPct != null) items.push({ label: "Fortschritt", value: `${d.scrollPct}%` });
          if (d.fontSize) items.push({ label: "Schrift", value: `${d.fontSize}%` });
          if (d.papier) items.push({ label: "Papier", value: d.papier, type: "papier" });
        } catch { items.push({ label: "Position", value: pos }); }
      } else {
        items.push({ label: "Fortschritt", value: `${rest}%` });
      }
    } else if (pos.startsWith("cfi:")) {
      items.push({ label: "EPUB-Position", value: "Gespeichert" });
    } else {
      const m = pos.match(/page:(\d+)/);
      if (m) items.push({ label: "Seite", value: m[1] });
      else items.push({ label: "Position", value: pos });
    }

    return { items, fontPreview };
  }
</script>

<div class="book-detail">
  <div class="page-header">
    <a href="/" class="back-link"><i class="fa-solid fa-arrow-left"></i> Bibliothek</a>
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
          <a href="/book/{book.id}/read" class="btn btn-primary">
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
            <i class="{book.is_favorite ? 'fa-solid' : 'fa-regular'} fa-heart"></i> Favorit
          </button>
          <button
            class="action-btn"
            class:active={book.is_to_read}
            onclick={onZumLesenToggle}
          >
            <i class="fa-solid {book.is_to_read ? 'fa-check' : 'fa-plus'}"></i> Leseliste
          </button>
          <button
            class="action-btn ai-btn"
            onclick={() => (aiDialogOpen = true)}
          >
            <i class="fa-solid fa-wand-magic-sparkles"></i> KI-Kategorisierung
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
                <a href="/?category={cat.id}" class="chip">{cat.name}</a>
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
                  href="/?tag={tag.id}"
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
          {@const pos = parseLeseposition(book.reading_position, book.file_format)}
          <div class="position-section">
            <h2 class="section-title">Lesefortschritt</h2>
            <div class="position-details">
              {#each pos.items as item}
                <div class="pos-item">
                  <span class="pos-label">{item.label}</span>
                  {#if item.type === "layout"}
                    <span class="pos-value pos-icon" title={item.value === "single" ? "Einzelseite" : "Doppelseite"}>
                      {#if item.value === "single"}
                        <svg width="16" height="14" viewBox="0 0 16 14"><rect x="3" y="0" width="10" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {:else}
                        <svg width="20" height="14" viewBox="0 0 20 14"><rect x="0.75" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="11.25" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {/if}
                    </span>
                  {:else if item.type === "pdf-ansicht"}
                    <span class="pos-value pos-icon" title={ansichtLabel[item.value] || item.value}>
                      {#if item.value === "scroll"}
                        <svg width="14" height="14" viewBox="0 0 14 14"><rect x="1" y="0" width="12" height="5.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><rect x="1" y="8.5" width="12" height="5.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
                      {:else if item.value === "breite"}
                        <svg width="18" height="14" viewBox="0 0 18 14"><rect x="0.75" y="1" width="16.5" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><line x1="4" y1="5" x2="14" y2="5" stroke="currentColor" stroke-width="1" opacity="0.4"/><line x1="4" y1="7.5" x2="12" y2="7.5" stroke="currentColor" stroke-width="1" opacity="0.4"/><line x1="4" y1="10" x2="13" y2="10" stroke="currentColor" stroke-width="1" opacity="0.4"/></svg>
                      {:else if item.value === "seite"}
                        <svg width="12" height="14" viewBox="0 0 12 14"><rect x="0.75" y="0" width="10.5" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
                      {:else if item.value === "einzeln"}
                        <svg width="16" height="14" viewBox="0 0 16 14"><rect x="3" y="0" width="10" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {:else if item.value === "doppel"}
                        <svg width="20" height="14" viewBox="0 0 20 14"><rect x="0.75" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="11.25" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {/if}
                    </span>
                  {:else if item.type === "papier"}
                    <span class="pos-value pos-papier pos-papier-{item.value}" title={papierLabel[item.value] || item.value}></span>
                  {:else}
                    <span class="pos-value">{item.value}</span>
                  {/if}
                </div>
              {/each}
              {#if pos.fontPreview}
                <div class="pos-item">
                  <span class="pos-label">Schriftart</span>
                  <span
                    class="pos-font-preview"
                    style="font-family: {pos.fontPreview.family}; {pos.fontPreview.fg ? `color: ${pos.fontPreview.fg};` : ''} {pos.fontPreview.bg ? `background-color: ${pos.fontPreview.bg};` : ''}"
                  >{pos.fontPreview.name}</span>
                </div>
              {/if}
            </div>
            <a href="/book/{book.id}/read" class="btn btn-secondary btn-sm">
              Weiterlesen
            </a>
          </div>
        {/if}
      </div>
    </div>

    <div class="notes-section">
        <NoteList bookId={book.id} />
      </div>

    <AiCategorizeDialog
      bookId={book.id}
      open={aiDialogOpen}
      onClose={() => (aiDialogOpen = false)}
      onDone={() => ladeBuch(book.id)}
    />
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

  .position-details {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.25rem 0.75rem;
    margin-bottom: 0.75rem;
    padding: 0.625rem 0.75rem;
    background-color: var(--color-bg-tertiary);
    border-radius: 6px;
    border: 1px solid var(--color-border);
  }

  .pos-item {
    display: contents;
  }

  .pos-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .pos-value {
    font-size: 0.75rem;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
  }

  .pos-icon {
    display: flex;
    align-items: center;
  }

  .pos-papier {
    width: 18px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid var(--color-border);
  }

  .pos-papier-normal {
    background-color: #ffffff;
  }

  .pos-papier-sepia {
    background-color: #f4ecd8;
  }

  .pos-papier-dunkel {
    background-color: #1e1e1e;
  }

  .pos-papier-kontrast {
    background-color: #000000;
  }

  .pos-font-preview {
    font-size: 0.8125rem;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    display: inline-block;
  }
</style>
