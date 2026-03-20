<script>
  import { ui } from "../lib/stores/ui.svelte.js";
  import { getToken, setToken } from "../lib/api/client.js";
  import { indexNeuAufbauen } from "../lib/api/search.js";
  import ServiceStatus from "../lib/components/settings/ServiceStatus.svelte";
  import BackupPanel from "../lib/components/settings/BackupPanel.svelte";

  let token = $state(getToken());
  let reindexMsg = $state("");

  function saveToken() {
    setToken(token);
  }

  async function reindex() {
    reindexMsg = "Index wird neu aufgebaut...";
    try {
      const result = await indexNeuAufbauen();
      reindexMsg = result.message || "Index neu aufgebaut";
    } catch (e) {
      reindexMsg = `Fehler: ${e.message}`;
    }
  }
</script>

<div class="settings-page">
  <div class="page-header">
    <h1>Einstellungen</h1>
  </div>

  <div class="settings-sections">
    <section class="settings-section">
      <h2>Darstellung</h2>
      <div class="setting-row">
        <label>Theme</label>
        <div class="theme-options">
          {#each ["light", "dark", "system"] as mode}
            <button
              class="theme-btn"
              class:active={ui.theme === mode}
              onclick={() => (ui.theme = mode)}
            >
              {mode === "light" ? "Hell" : mode === "dark" ? "Dunkel" : "System"}
            </button>
          {/each}
        </div>
      </div>
      <div class="setting-row">
        <label>Standardansicht</label>
        <div class="theme-options">
          <button
            class="theme-btn"
            class:active={ui.viewMode === "grid"}
            onclick={() => (ui.viewMode = "grid")}
          >
            Grid
          </button>
          <button
            class="theme-btn"
            class:active={ui.viewMode === "list"}
            onclick={() => (ui.viewMode = "list")}
          >
            Liste
          </button>
        </div>
      </div>
    </section>

    <section class="settings-section">
      <h2>Externe Dienste</h2>
      <ServiceStatus />
    </section>

    <section class="settings-section">
      <h2>API-Token</h2>
      <div class="token-row">
        <input
          type="text"
          class="token-input"
          bind:value={token}
          placeholder="API-Token eingeben"
        />
        <button class="save-btn" onclick={saveToken}>
          Speichern
        </button>
      </div>
    </section>

    <section class="settings-section">
      <h2>Datenbank</h2>
      <div class="setting-row">
        <button class="action-btn" onclick={reindex}>
          FTS-Index neu aufbauen
        </button>
        {#if reindexMsg}
          <span class="msg">{reindexMsg}</span>
        {/if}
      </div>
    </section>

    <section class="settings-section">
      <h2>Backup</h2>
      <BackupPanel />
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
    margin-bottom: 0.75rem;
  }

  .setting-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.375rem 0;
  }

  .setting-row label {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    min-width: 120px;
  }

  .theme-options {
    display: flex;
    gap: 0.375rem;
  }

  .theme-btn {
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
  }

  .theme-btn.active {
    background-color: var(--color-accent);
    color: #fff;
    border-color: var(--color-accent);
  }

  .token-row {
    display: flex;
    gap: 0.5rem;
  }

  .token-input {
    flex: 1;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 0.8125rem;
  }

  .save-btn,
  .action-btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
    cursor: pointer;
  }

  .save-btn:hover,
  .action-btn:hover {
    background-color: var(--color-accent);
    color: #fff;
  }

  .msg {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }
</style>
