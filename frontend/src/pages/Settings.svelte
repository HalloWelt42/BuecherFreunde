<script>
  import { ui } from "../lib/stores/ui.svelte.js";
  import { getToken, setToken } from "../lib/api/client.js";
  import { get } from "../lib/api/client.js";
  import { indexNeuAufbauen } from "../lib/api/search.js";
  import ServiceStatus from "../lib/components/settings/ServiceStatus.svelte";
  import BackupPanel from "../lib/components/settings/BackupPanel.svelte";
  import CategoryManager from "../lib/components/settings/CategoryManager.svelte";
  import TagManager from "../lib/components/settings/TagManager.svelte";
  import AiSettings from "../lib/components/settings/AiSettings.svelte";

  import { route } from "../lib/router.svelte.js";
  import { onMount } from "svelte";

  let activeTab = $derived.by(() => {
    if (route.path.includes("/settings/categories")) return "categories";
    if (route.path.includes("/settings/tags")) return "tags";
    if (route.path.includes("/settings/ai")) return "ai";
    return "general";
  });

  let token = $state(getToken());
  let reindexMsg = $state("");
  let paths = $state({ datenbank: "", speicher: "", import: "", extern: "" });
  let stats = $state({ buecher_gesamt: 0 });

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

  onMount(async () => {
    try {
      paths = await get("/api/config/paths");
    } catch { /* still */ }
    try {
      stats = await get("/api/config/stats");
    } catch { /* still */ }
  });
</script>

<div class="settings-page">
  <div class="page-header">
    <h1>
      <i class="fa-solid fa-gear"></i> Einstellungen
    </h1>
    <nav class="settings-tabs">
      <a href="/settings" class="tab" class:active={activeTab === "general"}>
        <i class="fa-solid fa-sliders"></i> Allgemein
      </a>
      <a href="/settings/categories" class="tab" class:active={activeTab === "categories"}>
        <i class="fa-solid fa-folder"></i> Kategorien
      </a>
      <a href="/settings/tags" class="tab" class:active={activeTab === "tags"}>
        <i class="fa-solid fa-tags"></i> Tags
      </a>
      <a href="/settings/ai" class="tab" class:active={activeTab === "ai"}>
        <i class="fa-solid fa-robot"></i> KI
      </a>
    </nav>
  </div>

  {#if activeTab === "categories"}
    <CategoryManager />
  {:else if activeTab === "tags"}
    <TagManager />
  {:else if activeTab === "ai"}
    <AiSettings />
  {:else}
    <div class="settings-grid">
      <!-- Linke Spalte -->
      <div class="settings-col">
        <section class="settings-section">
          <h2><i class="fa-solid fa-palette"></i> Darstellung</h2>
          <div class="setting-row">
            <span class="setting-label">Theme</span>
            <div class="btn-group">
              {#each [["light", "Hell", "fa-sun"], ["dark", "Dunkel", "fa-moon"], ["system", "System", "fa-display"]] as [mode, label, icon]}
                <button
                  class="seg-btn"
                  class:active={ui.theme === mode}
                  onclick={() => (ui.theme = mode)}
                >
                  <i class="fa-solid {icon}"></i> {label}
                </button>
              {/each}
            </div>
          </div>
          <div class="setting-row">
            <span class="setting-label">Standardansicht</span>
            <div class="btn-group">
              {#each [["grid", "Kacheln", "fa-table-cells"], ["list", "Liste", "fa-list"], ["covers", "Cover", "fa-image"]] as [mode, label, icon]}
                <button
                  class="seg-btn"
                  class:active={ui.viewMode === mode}
                  onclick={() => (ui.viewMode = mode)}
                >
                  <i class="fa-solid {icon}"></i> {label}
                </button>
              {/each}
            </div>
          </div>
        </section>

        <section class="settings-section">
          <h2><i class="fa-solid fa-key"></i> API-Token</h2>
          <div class="token-row">
            <input
              type="text"
              class="form-input mono"
              bind:value={token}
              placeholder="API-Token eingeben"
            />
            <button class="btn-primary" onclick={saveToken}>
              <i class="fa-solid fa-check"></i> Speichern
            </button>
          </div>
        </section>

        <section class="settings-section">
          <h2><i class="fa-solid fa-plug"></i> Externe Dienste</h2>
          <ServiceStatus />
        </section>
      </div>

      <!-- Rechte Spalte -->
      <div class="settings-col">
        <section class="settings-section">
          <h2><i class="fa-solid fa-hard-drive"></i> Verzeichnisse</h2>
          <div class="path-list">
            <div class="path-row">
              <span class="path-label">Datenbank</span>
              <code class="path-value">{paths.datenbank || "--"}</code>
              <span class="path-hint">SQLite-Datenbankdatei mit allen Metadaten, Einstellungen und dem Suchindex.</span>
            </div>
            <div class="path-row">
              <span class="path-label">Bücherspeicher</span>
              <code class="path-value">{paths.speicher || "--"}</code>
              <span class="path-hint">Hash-basierter Speicher für Originaldateien, Cover und Volltexte. Per rsync sicherbar.</span>
            </div>
            <div class="path-row">
              <span class="path-label">Import-Verzeichnis</span>
              <code class="path-value">{paths.import || "--"}</code>
              <span class="path-hint">Neue Dateien hier ablegen oder hochladen. Wird beim Import-Scan durchsucht.</span>
            </div>
            {#if paths.extern}
              <div class="path-row">
                <span class="path-label">Externes Verzeichnis</span>
                <code class="path-value">{paths.extern}</code>
                <span class="path-hint">Externer Mount (USB, Netzlaufwerk). Dient als zusätzliche Import-Quelle und zur Duplikaterkennung.</span>
              </div>
            {/if}
          </div>
          <div class="stats-row">
            <span class="stat"><strong>{stats.buecher_gesamt}</strong> Bücher</span>
          </div>
        </section>

        <section class="settings-section">
          <h2><i class="fa-solid fa-database"></i> Datenbank</h2>
          <div class="setting-row">
            <button class="btn-secondary" onclick={reindex}>
              <i class="fa-solid fa-rotate"></i> FTS-Index neu aufbauen
            </button>
            {#if reindexMsg}
              <span class="msg">{reindexMsg}</span>
            {/if}
          </div>
        </section>

        <section class="settings-section">
          <h2><i class="fa-solid fa-box-archive"></i> Backup</h2>
          <BackupPanel />
        </section>
      </div>
    </div>
  {/if}
</div>

<style>
  .settings-page {
    max-width: 1200px;
  }

  .page-header {
    margin-bottom: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .page-header h1 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .page-header h1 i {
    color: var(--color-accent);
  }

  .settings-tabs {
    display: flex;
    gap: 0.25rem;
    border-bottom: 1px solid var(--color-border);
  }

  .tab {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    border-bottom: 2px solid transparent;
    color: var(--color-text-secondary);
    text-decoration: none;
    font-size: 0.8125rem;
    font-weight: 500;
    transition: all 0.12s;
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--color-text-primary);
  }

  .tab.active {
    color: var(--color-accent);
    border-bottom-color: var(--color-accent);
  }

  /* 2-Spalten Grid */
  .settings-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    align-items: start;
  }

  @media (max-width: 900px) {
    .settings-grid {
      grid-template-columns: 1fr;
    }
  }

  .settings-col {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .settings-section {
    padding: 1rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-secondary);
  }

  .settings-section h2 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.75rem;
  }

  .settings-section h2 i {
    font-size: 0.8125rem;
    color: var(--color-accent);
    width: 1rem;
    text-align: center;
  }

  .setting-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.25rem 0;
  }

  .setting-label {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    min-width: 110px;
    flex-shrink: 0;
  }

  /* Segmented Buttons */
  .btn-group {
    display: flex;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    overflow: hidden;
  }

  .seg-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.3125rem 0.625rem;
    border: none;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.1s;
  }

  .seg-btn + .seg-btn {
    border-left: 1px solid var(--color-border);
  }

  .seg-btn:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .seg-btn.active {
    background-color: var(--color-accent);
    color: #fff;
  }

  /* Token */
  .token-row {
    display: flex;
    gap: 0.5rem;
  }

  .form-input {
    flex: 1;
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: var(--font-sans);
  }

  .form-input.mono {
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .form-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  /* Buttons */
  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border: none;
    border-radius: 6px;
    background-color: var(--color-accent);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: opacity 0.1s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.1s;
  }

  .btn-secondary:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
    border-color: var(--color-accent);
  }

  /* Pfade */
  .path-list {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .path-row {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    margin-bottom: 0.25rem;
  }

  .path-label {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .path-value {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background-color: var(--color-bg-primary);
    padding: 0.25rem 0.375rem;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    word-break: break-all;
  }

  .path-hint {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    line-height: 1.3;
  }

  .stats-row {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }

  .stat {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .stat strong {
    color: var(--color-text-primary);
    font-weight: 600;
  }

  .msg {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
</style>
