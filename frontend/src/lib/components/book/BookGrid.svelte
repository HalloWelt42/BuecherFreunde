<script>
  import BookCard from "./BookCard.svelte";
  import { coverUrl } from "../../api/books.js";
  import { selectionStore } from "../../stores/selection.svelte.js";

  let { books = [], large = false, coversOnly = false } = $props();

  // Drag-Select State
  let isDragging = $state(false);
  let dragMode = $state("add"); // "add" oder "remove"

  function handlePointerDown(e, bookId) {
    // Nur linke Maustaste, nicht auf Links/Buttons
    if (e.button !== 0) return;
    const tag = e.target.tagName.toLowerCase();
    if (tag === "button" || tag === "i" || e.target.closest("button")) return;

    e.preventDefault();
    isDragging = true;

    // Modus bestimmen: wenn bereits selektiert -> abwählen, sonst anwählen
    if (selectionStore.has(bookId)) {
      dragMode = "remove";
      selectionStore.remove(bookId);
    } else {
      dragMode = "add";
      selectionStore.add(bookId);
    }

    // Pointer Capture für zuverlässiges Tracking
    e.target.closest("[data-book-id]")?.setPointerCapture?.(e.pointerId);
  }

  function handlePointerEnter(bookId) {
    if (!isDragging) return;
    if (dragMode === "add") {
      selectionStore.add(bookId);
    } else {
      selectionStore.remove(bookId);
    }
  }

  function handlePointerUp() {
    isDragging = false;
  }

  // Cover-Only: Selection
  let coverErrors = $state(new Set());

  function setCoverError(bookId) {
    coverErrors = new Set([...coverErrors, bookId]);
  }
</script>

<svelte:window onpointerup={handlePointerUp} />

{#if books.length === 0}
  <div class="empty-state">
    <i class="fa-solid fa-book-open empty-icon"></i>
    <h3 class="empty-title">Keine Bücher gefunden</h3>
    <p class="empty-text">Passe die Filter an oder importiere neue Bücher.</p>
  </div>
{:else if coversOnly}
  <div class="cover-grid" class:drag-active={isDragging}>
    {#each books as book (book.id)}
      {@const isSelected = selectionStore.has(book.id)}
      <div
        class="cover-item"
        class:selected={isSelected}
        data-book-id={book.id}
        onpointerdown={(e) => handlePointerDown(e, book.id)}
        onpointerenter={() => handlePointerEnter(book.id)}
        role="button"
        tabindex="-1"
      >
        <!-- Checkbox -->
        <button
          class="cover-checkbox"
          class:visible={isSelected || selectionStore.active}
          onclick={(e) => { e.preventDefault(); e.stopPropagation(); selectionStore.toggle(book.id); }}
        >
          {#if isSelected}
            <i class="fa-solid fa-square-check"></i>
          {:else}
            <i class="fa-regular fa-square"></i>
          {/if}
        </button>

        <a href="/book/{book.id}" class="cover-link" onclick={(e) => { if (selectionStore.active) { e.preventDefault(); selectionStore.toggle(book.id); } }}>
          {#if !coverErrors.has(book.id)}
            <img
              src={coverUrl(book.id, book.updated_at)}
              alt={book.title}
              class="cover-img"
              loading="lazy"
              onerror={() => setCoverError(book.id)}
            />
          {:else}
            <div class="cover-placeholder">
              <i class="fa-solid fa-book"></i>
              <span class="cover-placeholder-title">{book.title}</span>
            </div>
          {/if}
        </a>

        <!-- Hover-Popup -->
        <div class="cover-popup">
          {#if !coverErrors.has(book.id)}
            <img src={coverUrl(book.id, book.updated_at)} alt="" class="popup-img" />
          {/if}
          <div class="popup-info">
            <strong class="popup-title">{book.title}</strong>
            {#if book.author}
              <span class="popup-author">{book.author}</span>
            {/if}
          </div>
        </div>
      </div>
    {/each}
  </div>
{:else}
  <div class="book-grid" class:large class:drag-active={isDragging}>
    {#each books as book (book.id)}
      <div
        data-book-id={book.id}
        onpointerdown={(e) => handlePointerDown(e, book.id)}
        onpointerenter={() => handlePointerEnter(book.id)}
      >
        <BookCard {book} />
      </div>
    {/each}
  </div>
{/if}

<style>
  .book-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
  }

  .book-grid.large {
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1.5rem;
  }

  /* Drag-Modus: Textauswahl verhindern */
  .drag-active {
    user-select: none;
    -webkit-user-select: none;
  }

  /* Cover-Only Grid */
  .cover-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 0.5rem;
  }

  .cover-item {
    aspect-ratio: 1 / 1.414;
    border-radius: 4px;
    overflow: hidden;
    background-color: var(--color-bg-tertiary);
    transition: transform 0.12s, box-shadow 0.12s;
    position: relative;
    cursor: pointer;
  }

  .cover-item:hover {
    transform: scale(1.04);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    z-index: 10;
  }

  .cover-item.selected {
    box-shadow: 0 0 0 3px var(--color-accent);
    transform: scale(1.02);
  }

  .cover-link {
    display: block;
    width: 100%;
    height: 100%;
  }

  .cover-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .cover-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    padding: 0.5rem;
    text-align: center;
    color: var(--color-text-muted);
    background: linear-gradient(135deg, var(--color-bg-tertiary), var(--color-bg-secondary));
  }

  .cover-placeholder i {
    font-size: 1.5rem;
    opacity: 0.4;
  }

  .cover-placeholder-title {
    font-size: 0.5625rem;
    font-weight: 600;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    line-height: 1.3;
  }

  /* Cover Checkbox */
  .cover-checkbox {
    position: absolute;
    top: 0.25rem;
    right: 0.25rem;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    border: none;
    border-radius: 3px;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    color: #fff;
    font-size: 0.875rem;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.12s;
  }

  .cover-checkbox.visible,
  .cover-item:hover .cover-checkbox {
    opacity: 1;
  }

  .cover-item.selected .cover-checkbox {
    opacity: 1;
    color: var(--color-accent);
    background: rgba(255, 255, 255, 0.9);
  }

  /* Hover-Popup fuer Cover-Only */
  .cover-popup {
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%) scale(0.9);
    width: 200px;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    overflow: hidden;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.15s, transform 0.15s;
    z-index: 50;
  }

  .cover-item:hover .cover-popup {
    opacity: 1;
    transform: translateX(-50%) scale(1);
  }

  .popup-img {
    width: 100%;
    aspect-ratio: 1 / 1.414;
    object-fit: cover;
  }

  .popup-info {
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .popup-title {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-primary);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.3;
  }

  .popup-author {
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    color: var(--color-text-muted);
    text-align: center;
    gap: 0.75rem;
  }

  .empty-icon {
    font-size: 3rem;
    opacity: 0.3;
  }

  .empty-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  .empty-text {
    font-size: 0.875rem;
    max-width: 300px;
  }
</style>
