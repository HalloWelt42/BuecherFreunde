<div class="settings-page">
  <div class="page-header">
    <h1>Einstellungen</h1>
  </div>

  <div class="settings-sections">
    <section class="settings-section">
      <h2>Darstellung</h2>
      <p class="placeholder">Theme, Akzentfarbe und Standardansicht</p>
    </section>

    <section class="settings-section">
      <h2>Externe Dienste</h2>
      <p class="placeholder">LM Studio, Open Library - Status und Konfiguration</p>
    </section>

    <section class="settings-section">
      <h2>Datenbank</h2>
      <p class="placeholder">Statistiken, FTS-Index, Backup</p>
    </section>
  </div>
</div>

<style>
  .settings-page {
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

  .settings-sections {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .settings-section {
    padding: 1.25rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-secondary);
  }

  .settings-section h2 {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.5rem;
  }

  .placeholder {
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }
</style>
