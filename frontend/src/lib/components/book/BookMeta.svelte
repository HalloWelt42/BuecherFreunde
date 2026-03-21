<script>
  let { book } = $props();

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  function formatDate(dateStr) {
    if (!dateStr) return "-";
    const d = new Date(dateStr);
    return d.toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }
</script>

<div class="meta-grid">
  <div class="meta-item">
    <span class="meta-label">Format</span>
    <span class="meta-value format">{(book.file_format || "").toUpperCase()}</span>
  </div>
  <div class="meta-item">
    <span class="meta-label">Größe</span>
    <span class="meta-value">{formatSize(book.file_size)}</span>
  </div>
  {#if book.page_count}
    <div class="meta-item">
      <span class="meta-label">Seiten</span>
      <span class="meta-value">{book.page_count}</span>
    </div>
  {/if}
  {#if book.isbn}
    <div class="meta-item">
      <span class="meta-label">ISBN</span>
      <span class="meta-value mono">{book.isbn}</span>
    </div>
  {/if}
  {#if book.year}
    <div class="meta-item">
      <span class="meta-label">Jahr</span>
      <span class="meta-value">{book.year}</span>
    </div>
  {/if}
  <div class="meta-item">
    <span class="meta-label">Hinzugefügt</span>
    <span class="meta-value">{formatDate(book.created_at)}</span>
  </div>
  {#if book.last_read_at}
    <div class="meta-item">
      <span class="meta-label">Zuletzt gelesen</span>
      <span class="meta-value">{formatDate(book.last_read_at)}</span>
    </div>
  {/if}
</div>

<style>
  .meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
  }

  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .meta-label {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .meta-value {
    font-size: 0.875rem;
    color: var(--color-text-primary);
  }

  .meta-value.format {
    font-family: var(--font-mono);
    font-weight: 700;
  }

  .meta-value.mono {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
  }
</style>
