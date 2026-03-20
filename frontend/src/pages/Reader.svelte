<script>
  import { router } from "svelte-spa-router";

  let { params } = $props();

  let position = $derived.by(() => {
    const qs = new URLSearchParams(router.querystring || "");
    return {
      page: qs.get("page"),
      cfi: qs.get("cfi"),
    };
  });
</script>

<div class="reader-page">
  <div class="reader-toolbar">
    <a href="#/book/{params.id}" class="back-link">&larr; Zurück zum Buch</a>
    <span class="reader-title">Reader - Buch #{params.id}</span>
    {#if position.page}
      <span class="position-info">Seite {position.page}</span>
    {/if}
  </div>
  <div class="reader-content">
    <p class="placeholder">Reader wird geladen...</p>
  </div>
</div>

<style>
  .reader-page {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .reader-toolbar {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--color-border);
    margin-bottom: 1rem;
  }

  .back-link {
    color: var(--color-accent);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .reader-title {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .position-info {
    margin-left: auto;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .reader-content {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .placeholder {
    color: var(--color-text-muted);
  }
</style>
