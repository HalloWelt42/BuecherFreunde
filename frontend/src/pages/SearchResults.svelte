<script>
  import { router } from "svelte-spa-router";

  let query = $derived.by(() => {
    const params = new URLSearchParams(router.querystring || "");
    return params.get("q") || "";
  });
</script>

<div class="search-page">
  <div class="page-header">
    <h1>Suchergebnisse</h1>
    {#if query}
      <p class="search-info">für "{query}"</p>
    {/if}
  </div>
  <div class="empty-state">
    {#if query}
      <p>Keine Ergebnisse für "{query}" gefunden.</p>
    {:else}
      <p>Bitte einen Suchbegriff eingeben.</p>
    {/if}
  </div>
</div>

<style>
  .page-header {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .search-info {
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }

  .empty-state {
    color: var(--color-text-secondary);
    padding: 2rem 0;
  }
</style>
