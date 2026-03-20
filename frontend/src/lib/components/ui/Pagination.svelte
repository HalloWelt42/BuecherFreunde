<script>
  let { total = 0, limit = 50, offset = 0, onPage = () => {} } = $props();

  let currentPage = $derived(Math.floor(offset / limit) + 1);
  let totalPages = $derived(Math.ceil(total / limit));

  function goTo(page) {
    const newOffset = (page - 1) * limit;
    onPage(newOffset);
  }
</script>

{#if totalPages > 1}
  <div class="pagination">
    <button
      class="page-btn"
      disabled={currentPage <= 1}
      onclick={() => goTo(currentPage - 1)}
    >
      &larr;
    </button>

    <span class="page-info">
      Seite {currentPage} von {totalPages}
      <span class="total-info">({total} Bücher)</span>
    </span>

    <button
      class="page-btn"
      disabled={currentPage >= totalPages}
      onclick={() => goTo(currentPage + 1)}
    >
      &rarr;
    </button>
  </div>
{/if}

<style>
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 1rem 0;
  }

  .page-btn {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 0.375rem 0.75rem;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
  }

  .page-btn:hover:not(:disabled) {
    background-color: var(--color-bg-tertiary);
  }

  .page-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .page-info {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  .total-info {
    color: var(--color-text-muted);
    font-size: 0.8125rem;
  }
</style>
