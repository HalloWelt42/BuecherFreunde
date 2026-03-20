<script>
  let { bookId, title = "", onBack = () => {} } = $props();
</script>

<div class="reader-toolbar">
  <button class="back-btn" onclick={onBack} title="Zurück">
    &larr;
  </button>
  <span class="toolbar-title">{title}</span>
  <div class="toolbar-actions">
    <a
      href="/api/books/{bookId}/file"
      download
      class="action-btn"
      title="Herunterladen"
    >
      Herunterladen
    </a>
  </div>
</div>

<style>
  .reader-toolbar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    flex-shrink: 0;
  }

  .back-btn {
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: var(--color-text-secondary);
    padding: 0.25rem;
  }

  .back-btn:hover {
    color: var(--color-accent);
  }

  .toolbar-title {
    flex: 1;
    font-weight: 600;
    font-size: 0.875rem;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .action-btn {
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    text-decoration: none;
  }

  .action-btn:hover {
    background-color: var(--color-bg-tertiary);
  }
</style>
