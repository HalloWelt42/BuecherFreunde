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
  let aktiveFilter = $state({});
  const limit = 20;

  const filterLabels = {
    autor: "Autor",
    format: "Format",
    jahr: "Jahr",
    zeitraum: "Zeitraum",
    ab_jahr: "Ab",
    bis_jahr: "Bis",
  };

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
      aktiveFilter = data.aktive_filter || {};
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

  {#if Object.keys(aktiveFilter).length > 0}
    <div class="active-filters">
      <span class="filter-label"><i class="fa-solid fa-filter"></i> Filter:</span>
      {#each Object.entries(aktiveFilter) as [key, value]}
        <span class="filter-tag">
          <span class="filter-key">{filterLabels[key] || key}</span>
          <span class="filter-value">{value}</span>
        </span>
      {/each}
    </div>
  {/if}

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

  .active-filters {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--glass-bg);
  }

  .filter-label {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .filter-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    background: color-mix(in srgb, var(--color-accent) 15%, transparent);
    font-size: 0.75rem;
  }

  .filter-key {
    color: var(--color-text-muted);
    font-weight: 500;
  }

  .filter-value {
    color: var(--color-accent);
    font-weight: 600;
  }
</style>
