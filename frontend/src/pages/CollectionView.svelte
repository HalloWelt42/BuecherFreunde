<script>
  import { holeSammlung } from "../lib/api/collections.js";
  import BookGrid from "../lib/components/book/BookGrid.svelte";
  import { ui } from "../lib/stores/ui.svelte.js";
  import BookList from "../lib/components/book/BookList.svelte";
  import ViewToggle from "../lib/components/ui/ViewToggle.svelte";

  let { params } = $props();

  let sammlung = $state(null);
  let laden = $state(true);
  let fehler = $state(null);

  $effect(() => {
    ladeSammlung(Number(params.id));
  });

  async function ladeSammlung(id) {
    laden = true;
    fehler = null;
    try {
      sammlung = await holeSammlung(id);
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }
</script>

<div class="collection-page">
  <div class="page-header">
    <a href="/" class="back-link">&larr; Bibliothek</a>
    {#if sammlung}
      <h1>{sammlung.name}</h1>
      {#if sammlung.description}
        <p class="description">{sammlung.description}</p>
      {/if}
    {/if}
    <div class="header-actions">
      <ViewToggle />
    </div>
  </div>

  {#if laden}
    <p class="status">Sammlung wird geladen...</p>
  {:else if fehler}
    <p class="status error">{fehler}</p>
  {:else if sammlung}
    {#if sammlung.books && sammlung.books.length > 0}
      {#if ui.viewMode === "grid"}
        <BookGrid books={sammlung.books} />
      {:else}
        <BookList books={sammlung.books} />
      {/if}
    {:else}
      <p class="status">Diese Sammlung ist noch leer.</p>
    {/if}
  {/if}
</div>

<style>
  .collection-page {
    max-width: 960px;
  }

  .page-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    position: sticky;
    top: -1.5rem;
    z-index: 10;
    background-color: var(--color-bg-primary);
    margin: -1.5rem -1.5rem 1.5rem;
    padding: 1.5rem 1.5rem 0.75rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .back-link {
    color: var(--color-accent);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .description {
    width: 100%;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  .header-actions {
    margin-left: auto;
  }

  .status {
    color: var(--color-text-muted);
    padding: 2rem 0;
  }

  .status.error {
    color: var(--color-error);
  }
</style>
