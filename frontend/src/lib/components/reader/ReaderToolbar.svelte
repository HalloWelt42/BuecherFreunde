<script>
  let { bookId, title = "", onBack = () => {} } = $props();
</script>

<div class="reader-toolbar">
  <button class="back-btn" onclick={onBack} title="Zurück">
    <i class="fa-solid fa-arrow-left"></i>
  </button>
  <span class="toolbar-title" title={title}>{title}</span>
  <div class="toolbar-actions">
    <a
      href="/api/books/{bookId}/file"
      download
      class="action-btn"
      title="Herunterladen"
    >
      <i class="fa-solid fa-download"></i>
    </a>
  </div>
</div>

<style>
  .reader-toolbar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0 0.5rem;
    height: 36px;
    border-bottom: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    flex-shrink: 0;
  }

  .back-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
  }

  .back-btn:hover {
    color: var(--color-accent);
    background-color: var(--color-bg-tertiary);
  }

  .toolbar-title {
    flex: 1;
    font-weight: 600;
    font-size: 0.8125rem;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    text-decoration: none;
  }

  .action-btn:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }
</style>
