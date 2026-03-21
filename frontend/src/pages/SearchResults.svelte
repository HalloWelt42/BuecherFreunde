<script>
  import { suche } from "../lib/api/search.js";
  import { coverUrl } from "../lib/api/books.js";
  import SearchSnippet from "../lib/components/search/SearchSnippet.svelte";
  import Pagination from "../lib/components/ui/Pagination.svelte";

  import { route } from "../lib/router.svelte.js";

  let query = $derived.by(() => {
    const params = new URLSearchParams(route.qs || "");
    return params.get("q") || "";
  });

  let results = $state([]);
  let total = $state(0);
  let laden = $state(false);
  let fehler = $state(null);
  let offset = $state(0);
  const limit = 20;

  $effect(() => {
    if (query) {
      offset = 0;
      sucheAusfuehren(query, 0);
    } else {
      results = [];
      total = 0;
    }
  });

  async function sucheAusfuehren(q, off) {
    laden = true;
    fehler = null;
    try {
      const data = await suche(q, { limit, offset: off });
      results = data.treffer || data.results || [];
      total = data.gesamt ?? data.total ?? 0;
    } catch (e) {
      fehler = e.message;
      results = [];
    } finally {
      laden = false;
    }
  }

  function onPage(newOffset) {
    offset = newOffset;
    sucheAusfuehren(query, newOffset);
  }
</script>

<div class="search-page">
  <div class="page-header">
    <h1>Suchergebnisse</h1>
    {#if query}
      <p class="search-info">
        {#if total > 0}
          {total} Treffer für "{query}"
        {:else if !laden}
          Keine Treffer für "{query}"
        {/if}
      </p>
    {/if}
  </div>

  {#if laden}
    <div class="loading">Suche läuft...</div>
  {:else if fehler}
    <div class="error">Fehler: {fehler}</div>
  {:else if !query}
    <div class="empty">Bitte einen Suchbegriff eingeben.</div>
  {:else}
    <div class="results-list">
      {#each results as result (result.book_id)}
        <a href="/book/{result.book_id}" class="result-item">
          <div class="result-cover">
            <img
              src={coverUrl(result.book_id)}
              alt=""
              loading="lazy"
              onerror={(e) => (e.target.style.display = "none")}
            />
          </div>
          <div class="result-content">
            <h3 class="result-title">{result.titel}</h3>
            <p class="result-author">{result.autor || "Unbekannt"}</p>
            {#if result.snippet}
              <SearchSnippet snippet={result.snippet} />
            {/if}
            <div class="result-meta">
              <span class="relevance">
                Relevanz: {Math.round(result.relevanz * 100)}%
              </span>
            </div>
          </div>
        </a>
      {/each}
    </div>

    <Pagination {total} {limit} {offset} {onPage} />
  {/if}
</div>

<style>
  .search-page {
    max-width: 800px;
  }

  .page-header {
    display: flex;
    align-items: baseline;
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

  .search-info {
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }

  .loading,
  .error,
  .empty {
    color: var(--color-text-muted);
    padding: 2rem 0;
  }

  .error {
    color: var(--color-error);
  }

  .results-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .result-item {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    text-decoration: none;
    color: inherit;
    transition: background-color 0.15s;
  }

  .result-item:hover {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
  }

  .result-cover {
    width: 56px;
    height: 84px;
    flex-shrink: 0;
    border-radius: 4px;
    overflow: hidden;
    background-color: var(--color-bg-tertiary);
  }

  .result-cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .result-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .result-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .result-author {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .result-meta {
    margin-top: 0.25rem;
  }

  .relevance {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
  }
</style>
