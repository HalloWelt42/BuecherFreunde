<script>
  import { router } from "svelte-spa-router";
  import { ui } from "../lib/stores/ui.svelte.js";
  import { booksStore } from "../lib/stores/books.svelte.js";
  import BookGrid from "../lib/components/book/BookGrid.svelte";
  import BookList from "../lib/components/book/BookList.svelte";
  import ContinueReading from "../lib/components/book/ContinueReading.svelte";
  import ViewToggle from "../lib/components/ui/ViewToggle.svelte";
  import Pagination from "../lib/components/ui/Pagination.svelte";

  // URL-Parameter als Filter übernehmen
  $effect(() => {
    const params = new URLSearchParams(router.querystring || "");
    const newFilter = {};
    if (params.get("category")) newFilter.category_id = Number(params.get("category"));
    if (params.get("tag")) newFilter.tag_id = Number(params.get("tag"));
    if (params.get("is_favorite")) newFilter.is_favorite = true;
    if (params.get("is_to_read")) newFilter.is_to_read = true;
    if (params.get("min_rating")) newFilter.min_rating = Number(params.get("min_rating"));
    if (params.get("file_format")) newFilter.file_format = params.get("file_format");
    booksStore.setFilter(newFilter);
  });

  function onPage(offset) {
    booksStore.setFilter({ ...booksStore.filter, offset });
  }
</script>

<div class="library-page">
  <div class="page-header">
    <h1>Bibliothek</h1>
    <div class="header-actions">
      <span class="book-count">
        {booksStore.total} Bücher
      </span>
      <ViewToggle />
    </div>
  </div>

  {#if booksStore.laden}
    <div class="loading-state">
      <p>Bücher werden geladen...</p>
    </div>
  {:else if booksStore.fehler}
    <div class="error-state">
      <p>Fehler: {booksStore.fehler}</p>
      <button onclick={() => booksStore.laden_()}>Erneut versuchen</button>
    </div>
  {:else if booksStore.books.length === 0}
    <div class="empty-state">
      <p class="empty-icon">{"\u{1F4DA}"}</p>
      <h2>Willkommen bei BücherFreunde</h2>
      <p>Importiere dein erstes Buch, um loszulegen.</p>
      <a href="#/import" class="import-link">Bücher importieren</a>
    </div>
  {:else}
    <ContinueReading />

    {#if ui.viewMode === "grid"}
      <BookGrid books={booksStore.books} />
    {:else}
      <BookList
        books={booksStore.books}
        onSort={(col, dir) => booksStore.setFilter({ sort_by: col, sort_dir: dir })}
      />
    {/if}

    <Pagination
      total={booksStore.total}
      limit={booksStore.filter.limit}
      offset={booksStore.filter.offset}
      {onPage}
    />
  {/if}
</div>

<style>
  .library-page {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
    flex-shrink: 0;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .book-count {
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }

  .loading-state,
  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem;
    gap: 1rem;
    color: var(--color-text-secondary);
  }

  .error-state button {
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
    cursor: pointer;
  }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: var(--color-text-secondary);
    gap: 0.5rem;
  }

  .empty-icon {
    font-size: 3rem;
    margin-bottom: 0.5rem;
  }

  .empty-state h2 {
    font-size: 1.25rem;
    font-weight: 600;
  }

  .import-link {
    margin-top: 1rem;
    padding: 0.5rem 1.25rem;
    background-color: var(--color-accent);
    color: #fff;
    border-radius: 6px;
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .import-link:hover {
    opacity: 0.9;
  }
</style>
