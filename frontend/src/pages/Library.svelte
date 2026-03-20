<script>
  import { router } from "svelte-spa-router";

  let filters = $derived.by(() => {
    const params = new URLSearchParams(router.querystring || "");
    return {
      category: params.get("category"),
      tag: params.get("tag"),
    };
  });
</script>

<div class="library-page">
  <div class="page-header">
    <h1>Bibliothek</h1>
    {#if filters.category || filters.tag}
      <p class="filter-info">
        Gefiltert
        {#if filters.category}nach Kategorie {filters.category}{/if}
        {#if filters.tag}nach Tag {filters.tag}{/if}
      </p>
    {/if}
  </div>

  <div class="empty-state">
    <p class="empty-icon">{"\u{1F4DA}"}</p>
    <h2>Willkommen bei BücherFreunde</h2>
    <p>Importiere dein erstes Buch, um loszulegen.</p>
    <a href="#/import" class="import-link">Bücher importieren</a>
  </div>
</div>

<style>
  .library-page {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .page-header {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .filter-info {
    font-size: 0.875rem;
    color: var(--color-text-muted);
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
