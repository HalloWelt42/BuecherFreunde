<div class="import-page">
  <div class="page-header">
    <h1>Import</h1>
  </div>

  <div class="upload-zone">
    <p class="upload-icon">{"\u{1F4E4}"}</p>
    <p class="upload-text">Bücher hierher ziehen oder klicken zum Auswählen</p>
    <p class="upload-hint">PDF, EPUB, MOBI, TXT, MD</p>
  </div>

  <div class="import-actions">
    <button class="action-btn">Import-Verzeichnis scannen</button>
    <button class="action-btn">Externes Verzeichnis scannen</button>
  </div>
</div>

<style>
  .import-page {
    max-width: 800px;
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .upload-zone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 2rem;
    border: 2px dashed var(--color-border);
    border-radius: 12px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.15s;
    margin-bottom: 1.5rem;
  }

  .upload-zone:hover {
    border-color: var(--color-accent);
  }

  .upload-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
  }

  .upload-text {
    color: var(--color-text-secondary);
    font-size: 0.9375rem;
  }

  .upload-hint {
    color: var(--color-text-muted);
    font-size: 0.8125rem;
    margin-top: 0.375rem;
  }

  .import-actions {
    display: flex;
    gap: 0.75rem;
  }

  .action-btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .action-btn:hover {
    background-color: var(--color-bg-tertiary);
  }
</style>
