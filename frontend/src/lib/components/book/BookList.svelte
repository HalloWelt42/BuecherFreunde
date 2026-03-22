<script>
  import RatingStars from "../ui/RatingStars.svelte";
  import { coverUrl } from "../../api/books.js";
  import { selectionStore } from "../../stores/selection.svelte.js";

  let { books = [], onSort = null, detailed = false } = $props();

  let sortColumn = $state("title");
  let sortDir = $state("asc");

  // Drag-Select State
  let isDragging = $state(false);
  let dragMode = $state("add");

  function suppressNextClick() {
    function handler(e) {
      e.preventDefault();
      e.stopPropagation();
      window.removeEventListener("click", handler, true);
    }
    window.addEventListener("click", handler, true);
    setTimeout(() => window.removeEventListener("click", handler, true), 300);
  }

  let listEl = $state(null);

  function handlePointerDown(e, bookId) {
    if (!selectionStore.editMode) return;
    if (e.button !== 0) return;
    const tag = e.target.tagName.toLowerCase();
    if (tag === "button" || e.target.closest("button")) return;

    e.preventDefault();
    e.stopPropagation();
    suppressNextClick();
    isDragging = true;

    if (selectionStore.has(bookId)) {
      dragMode = "remove";
      selectionStore.remove(bookId);
    } else {
      dragMode = "add";
      selectionStore.add(bookId);
    }
  }

  function handlePointerEnter(bookId) {
    if (!isDragging) return;
    if (dragMode === "add") {
      selectionStore.add(bookId);
    } else {
      selectionStore.remove(bookId);
    }
  }

  function handleListPointerMove(e) {
    if (!isDragging) return;
    // Bei Pointer-Capture kommen keine pointerenter-Events,
    // daher manuell per elementFromPoint die Zeile ermitteln
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el) return;
    const row = el.closest("[data-book-id]");
    if (row) {
      const bookId = parseInt(row.dataset.bookId, 10);
      if (dragMode === "add") {
        selectionStore.add(bookId);
      } else {
        selectionStore.remove(bookId);
      }
    }
  }

  function handlePointerUp() {
    isDragging = false;
  }

  function handleSort(column) {
    if (sortColumn === column) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortColumn = column;
      sortDir = "asc";
    }
    if (onSort) {
      onSort(sortColumn, sortDir);
    }
  }

  function sortIcon(column) {
    if (sortColumn !== column) return "fa-sort";
    return sortDir === "asc" ? "fa-sort-up" : "fa-sort-down";
  }

  function formatSize(bytes) {
    if (!bytes) return "-";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  const formatLabel = {
    pdf: "PDF",
    epub: "EPUB",
    mobi: "MOBI",
    txt: "TXT",
    md: "MD",
  };

  function positionPopup(container) {
    const popup = container.querySelector('.cover-hover-popup');
    if (!popup) return;
    const rect = container.getBoundingClientRect();
    const popupW = 320;
    const popupH = 453;
    const viewW = window.innerWidth;
    const viewH = window.innerHeight;
    const headerH = 56;
    const margin = 8;

    // Vertikal: zentriert am Cover, eingegrenzt auf sichtbaren Bereich
    let top = rect.top + rect.height / 2 - popupH / 2;
    if (top < headerH + margin) top = headerH + margin;
    if (top + popupH > viewH - margin) top = viewH - popupH - margin;

    // Horizontal: rechts vom Cover, falls kein Platz dann links
    let left = rect.right + margin;
    if (left + popupW > viewW - margin) {
      left = rect.left - popupW - margin;
    }
    if (left < margin) left = margin;

    popup.style.position = 'fixed';
    popup.style.left = left + 'px';
    popup.style.top = top + 'px';
    popup.style.transform = 'none';
  }
</script>

<svelte:window onpointerup={handlePointerUp} onpointermove={handleListPointerMove} />

{#if books.length === 0}
  <div class="empty">
    <i class="fa-solid fa-book-open empty-icon"></i>
    <p>Keine Bücher gefunden.</p>
  </div>
{:else if detailed}
  <!-- Detailliste mit Drag-Selection -->
  <div class="detail-list" class:edit-mode={selectionStore.editMode} class:drag-active={isDragging} bind:this={listEl} onpointermove={handleListPointerMove} ondragstart={(e) => selectionStore.editMode && e.preventDefault()}>
    {#each books as book (book.id)}
      {@const isSelected = selectionStore.has(book.id)}
      <div
        class="detail-row"
        class:selected={isSelected}
        data-book-id={book.id}
        role="row"
        tabindex="-1"
        onpointerdown={(e) => handlePointerDown(e, book.id)}
        onpointerenter={() => handlePointerEnter(book.id)}
      >
        <div class="detail-cover-wrap" role="img" onmouseenter={(e) => positionPopup(e.currentTarget)}>
          <a href="/book/{book.id}" class="detail-link">
            <div class="detail-cover">
              <img
                src={coverUrl(book.id, book.updated_at)}
                alt=""
                class="detail-cover-img"
                loading="lazy"
                onerror={(e) => { e.target.style.display = "none"; e.target.nextElementSibling.style.display = "flex"; }}
              />
              <div class="detail-cover-placeholder" style="display: none;">
                <i class="fa-solid fa-book"></i>
              </div>
            </div>
          </a>
          <div class="cover-hover-popup">
            <img
              src={coverUrl(book.id, book.updated_at)}
              alt={book.title}
              class="cover-hover-img"
              onerror={(e) => (e.target.parentElement.style.display = "none")}
            />
          </div>
        </div>

        <a href="/book/{book.id}" class="detail-info">
          <div class="detail-header">
            <h3 class="detail-title">{book.title}</h3>
            <span class="detail-format">{formatLabel[book.file_format] || book.file_format}</span>
          </div>
          <p class="detail-author">{book.author || "Unbekannter Autor"}</p>

          <div class="detail-meta">
            <RatingStars rating={book.rating} size="small" />
            {#if book.page_count}
              <span class="detail-meta-item">
                <i class="fa-solid fa-file-lines"></i> {book.page_count} S.
              </span>
            {/if}
            <span class="detail-meta-item">
              {formatSize(book.file_size)}
            </span>
            {#if book.year}
              <span class="detail-meta-item">
                <i class="fa-solid fa-calendar"></i> {book.year}
              </span>
            {/if}
            {#if book.publisher}
              <span class="detail-meta-item">
                <i class="fa-solid fa-building"></i> {book.publisher}
              </span>
            {/if}
            {#if book.isbn}
              <span class="detail-meta-item isbn">
                <i class="fa-solid fa-barcode"></i> {book.isbn}
              </span>
            {/if}
          </div>

          {#if book.categories && book.categories.length > 0}
            <div class="detail-categories">
              {#each book.categories as cat (cat.id)}
                <span class="detail-chip">{cat.name}</span>
              {/each}
            </div>
          {/if}
        </a>

        <div class="detail-actions">
          {#if book.is_favorite}
            <i class="fa-solid fa-heart detail-fav"></i>
          {/if}
          {#if book.is_to_read}
            <i class="fa-solid fa-bookmark detail-bookmark"></i>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{:else}
  <!-- Kompakte Tabelle mit Drag-Selection -->
  <div class="table-wrapper" class:edit-mode={selectionStore.editMode} class:drag-active={isDragging} bind:this={listEl} onpointermove={handleListPointerMove} ondragstart={(e) => selectionStore.editMode && e.preventDefault()}>
    <table class="book-table">
      <thead>
        <tr>
          <th class="col-cover"></th>
          <th class="col-title sortable" onclick={() => handleSort("title")} title="Nach Titel sortieren">
            Titel <i class="fa-solid {sortIcon('title')} sort-icon"></i>
          </th>
          <th class="col-author sortable" onclick={() => handleSort("author")} title="Nach Autor sortieren">
            Autor <i class="fa-solid {sortIcon('author')} sort-icon"></i>
          </th>
          <th class="col-format" title="Dateiformat">Format</th>
          <th class="col-size sortable" onclick={() => handleSort("file_size")} title="Nach Dateigröße sortieren">
            Größe <i class="fa-solid {sortIcon('file_size')} sort-icon"></i>
          </th>
          <th class="col-rating sortable" onclick={() => handleSort("rating")} title="Nach Bewertung sortieren">
            Bewertung <i class="fa-solid {sortIcon('rating')} sort-icon"></i>
          </th>
          <th class="col-year sortable" onclick={() => handleSort("year")} title="Nach Erscheinungsjahr sortieren">
            Jahr <i class="fa-solid {sortIcon('year')} sort-icon"></i>
          </th>
        </tr>
      </thead>
      <tbody>
        {#each books as book (book.id)}
          {@const isSelected = selectionStore.has(book.id)}
          <tr
            class:selected={isSelected}
            data-book-id={book.id}
            onpointerdown={(e) => handlePointerDown(e, book.id)}
            onpointerenter={() => handlePointerEnter(book.id)}
          >
            <td class="col-cover">
              <div class="cover-cell"
                role="img"
                onmouseenter={(e) => positionPopup(e.currentTarget)}
              >
                <a href="/book/{book.id}" class="cover-link">
                  <img
                    src={coverUrl(book.id, book.updated_at)}
                    alt=""
                    class="mini-cover"
                    loading="lazy"
                    onerror={(e) => { e.target.style.display = "none"; e.target.nextElementSibling.style.display = "flex"; }}
                  />
                  <div class="mini-cover-placeholder" style="display: none;">
                    <i class="fa-solid fa-book"></i>
                  </div>
                </a>
                <div class="cover-hover-popup">
                  <img
                    src={coverUrl(book.id, book.updated_at)}
                    alt={book.title}
                    class="cover-hover-img"
                    onerror={(e) => (e.target.parentElement.style.display = "none")}
                  />
                </div>
              </div>
            </td>
            <td class="col-title">
              <a href="/book/{book.id}" class="title-link">
                {book.title}
              </a>
            </td>
            <td class="col-author">{book.author || "Unbekannt"}</td>
            <td class="col-format">
              <span class="format-tag">
                {formatLabel[book.file_format] || book.file_format}
              </span>
            </td>
            <td class="col-size">{formatSize(book.file_size)}</td>
            <td class="col-rating">
              <RatingStars rating={book.rating} size="small" />
            </td>
            <td class="col-year">{book.year || "-"}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  /* Edit-Modus: Textauswahl verhindern */
  .edit-mode {
    user-select: none;
    -webkit-user-select: none;
    cursor: crosshair;
  }

  .edit-mode :global(a) {
    -webkit-user-drag: none;
    cursor: crosshair;
  }

  .edit-mode :global(img) {
    -webkit-user-drag: none;
    pointer-events: none;
  }

  .drag-active {
    user-select: none;
    -webkit-user-select: none;
    cursor: crosshair;
  }

  /* Kompakte Tabelle */
  .table-wrapper {
    overflow-x: auto;
  }

  .book-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
  }

  .book-table th {
    text-align: left;
    font-weight: 600;
    color: var(--color-text-muted);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.5rem;
    border-bottom: 2px solid var(--color-border);
    white-space: nowrap;
  }

  .book-table th.sortable {
    cursor: pointer;
    user-select: none;
  }

  .book-table th.sortable:hover {
    color: var(--color-text-primary);
  }

  .sort-icon {
    font-size: 0.5rem;
    opacity: 0.5;
    margin-left: 0.125rem;
  }

  .book-table td {
    padding: 0.375rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    vertical-align: middle;
  }

  .book-table tbody tr:hover {
    background-color: var(--color-bg-tertiary);
  }

  .book-table tbody tr.selected {
    background-color: color-mix(in srgb, var(--color-warning, #f59e0b) 10%, transparent);
  }

  .book-table tbody tr.selected td {
    border-color: color-mix(in srgb, var(--color-warning, #f59e0b) 30%, transparent);
  }

  .col-cover {
    width: 48px;
  }

  .cover-cell {
    position: relative;
    width: 40px;
    height: 57px;
  }

  .cover-link {
    display: block;
    width: 100%;
    height: 100%;
  }

  .mini-cover {
    width: 40px;
    height: 57px;
    object-fit: cover;
    border-radius: 3px;
  }

  .mini-cover-placeholder {
    width: 40px;
    height: 57px;
    border-radius: 3px;
    background: linear-gradient(135deg, var(--color-bg-tertiary), var(--color-bg-secondary));
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-text-muted);
    font-size: 0.875rem;
    opacity: 0.4;
  }

  .cover-hover-popup {
    position: fixed;
    width: 320px;
    height: 453px;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.4);
    border: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.15s;
    z-index: 200;
  }

  .cover-cell:hover .cover-hover-popup,
  .detail-cover-wrap:hover .cover-hover-popup {
    opacity: 1;
  }

  .detail-cover-wrap {
    position: relative;
    flex-shrink: 0;
  }

  .cover-hover-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .title-link {
    color: var(--color-text-primary);
    text-decoration: none;
    font-weight: 500;
  }

  .title-link:hover {
    color: var(--color-accent);
  }

  .col-author {
    color: var(--color-text-secondary);
  }

  .format-tag {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    padding: 0.0625rem 0.3125rem;
    border-radius: 3px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  .col-size {
    color: var(--color-text-muted);
    white-space: nowrap;
    font-size: 0.75rem;
  }

  .col-year {
    color: var(--color-text-muted);
    font-size: 0.75rem;
  }

  /* Detailliste */
  .detail-list {
    display: flex;
    flex-direction: column;
  }

  .detail-row {
    display: flex;
    gap: 0.75rem;
    padding: 0.75rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    color: inherit;
    transition: background-color 0.08s;
    align-items: flex-start;
    position: relative;
  }

  .detail-row:hover {
    background-color: var(--color-bg-tertiary);
  }

  .detail-row.selected {
    background-color: color-mix(in srgb, var(--color-warning, #f59e0b) 10%, transparent);
    border-color: color-mix(in srgb, var(--color-warning, #f59e0b) 30%, transparent);
  }

  .detail-link {
    flex-shrink: 0;
    text-decoration: none;
  }

  .detail-cover {
    flex-shrink: 0;
    width: 56px;
    height: 80px;
    border-radius: 4px;
    overflow: hidden;
    background-color: var(--color-bg-tertiary);
  }

  .detail-cover-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .detail-cover-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-text-muted);
    font-size: 1.25rem;
    opacity: 0.4;
  }

  .detail-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    text-decoration: none;
    color: inherit;
  }

  .detail-header {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .detail-title {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .detail-format {
    flex-shrink: 0;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 700;
    padding: 0.0625rem 0.3125rem;
    border-radius: 3px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  .detail-author {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .detail-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.125rem;
    flex-wrap: wrap;
  }

  .detail-meta-item {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
  }

  .detail-meta-item i {
    font-size: 0.5625rem;
  }

  .detail-meta-item.isbn {
    font-family: var(--font-mono);
    font-size: 0.625rem;
  }

  .detail-categories {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin-top: 0.25rem;
  }

  .detail-chip {
    font-size: 0.5625rem;
    padding: 0.0625rem 0.375rem;
    border-radius: 999px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  .detail-chip.more {
    color: var(--color-accent);
    font-weight: 600;
  }

  .detail-actions {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.375rem;
    padding-top: 0.25rem;
    flex-shrink: 0;
  }

  .detail-fav {
    color: var(--color-favorite);
    font-size: 0.75rem;
  }

  .detail-bookmark {
    color: var(--color-accent);
    font-size: 0.75rem;
  }

  /* Empty */
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    color: var(--color-text-muted);
    gap: 0.5rem;
  }

  .empty-icon {
    font-size: 2rem;
    opacity: 0.3;
  }
</style>
