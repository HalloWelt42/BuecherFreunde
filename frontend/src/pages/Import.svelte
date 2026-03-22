<script>
  import UploadZone from "../lib/components/import/UploadZone.svelte";
  import ImportStatus from "../lib/components/import/ImportStatus.svelte";
  import ImportProgress from "../lib/components/import/ImportProgress.svelte";
  import GutenbergImport from "../lib/components/import/GutenbergImport.svelte";
  import {
    ladeDateienHoch,
    scanneImportVerzeichnis,
    scanneExternesVerzeichnis,
    holeImportStatus,
    importEvents,
    bereinigeImportTasks,
  } from "../lib/api/imports.js";

  let activeTab = $state("dateien");
  let tasks = $state([]);
  let laden = $state(false);
  let fehler = $state(null);
  let sseConnection = $state(null);

  import { onMount, onDestroy } from "svelte";

  onMount(() => {
    aktualisiereStatus();
    starteSSE();
  });

  onDestroy(() => {
    sseConnection?.close();
  });

  async function aktualisiereStatus() {
    try {
      const result = await holeImportStatus();
      tasks = result.aufgaben || result.tasks || (Array.isArray(result) ? result : []);
    } catch {
      // Beim ersten Laden noch keine Tasks
    }
  }

  function starteSSE() {
    sseConnection?.close();
    sseConnection = importEvents(
      (event) => {
        const d = event.data;
        if (d && d.aufgaben) {
          tasks = d.aufgaben;
        } else if (d && d.id) {
          const idx = tasks.findIndex((t) => t.id === d.id);
          if (idx >= 0) {
            tasks[idx] = d;
            tasks = [...tasks];
          } else {
            tasks = [...tasks, d];
          }
        }
      },
      () => {
        setTimeout(starteSSE, 5000);
      },
    );
  }

  async function onFiles(files) {
    laden = true;
    fehler = null;
    try {
      const neueTasks = await ladeDateienHoch(files);
      tasks = [...(Array.isArray(neueTasks) ? neueTasks : [neueTasks]), ...tasks];
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  async function scanImport() {
    laden = true;
    fehler = null;
    try {
      const result = await scanneImportVerzeichnis();
      const neueTasks = result.aufgaben || result.tasks || [];
      if (neueTasks.length > 0) {
        tasks = [...neueTasks, ...tasks];
      }
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  async function scanExtern() {
    laden = true;
    fehler = null;
    try {
      const result = await scanneExternesVerzeichnis();
      const neueTasks = result.aufgaben || result.tasks || [];
      if (neueTasks.length > 0) {
        tasks = [...neueTasks, ...tasks];
      }
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }
</script>

<div class="import-page">
  <div class="page-header">
    <h1>Import</h1>
    <div class="tab-bar">
      <button
        class="tab-btn"
        class:active={activeTab === "dateien"}
        onclick={() => activeTab = "dateien"}
      >
        <i class="fa-solid fa-file-import"></i> Dateien
      </button>
      <button
        class="tab-btn"
        class:active={activeTab === "gutenberg"}
        onclick={() => activeTab = "gutenberg"}
      >
        <i class="fa-solid fa-landmark-dome"></i> Gutenberg
      </button>
    </div>
  </div>

  {#if activeTab === "dateien"}
    <UploadZone {onFiles} />

    {#if fehler}
      <div class="error-banner">
        <p>{fehler}</p>
      </div>
    {/if}

    <div class="scan-actions">
      <button class="action-btn" onclick={scanImport} disabled={laden}>
        <i class="fa-solid fa-folder-open"></i> Import-Verzeichnis scannen
      </button>
      <button class="action-btn" onclick={scanExtern} disabled={laden}>
        <i class="fa-solid fa-hard-drive"></i> Externes Verzeichnis scannen
      </button>
    </div>

    {#if tasks.length > 0}
      <ImportProgress {tasks} />

      {@const fertige = tasks.filter(t => t.status === "fertig" || t.status === "fehler").length}
      <div class="tasks-header">
        <span class="tasks-count">{tasks.length} Aufgaben</span>
        {#if fertige > 0}
          <button class="action-btn clear-btn" onclick={async () => { try { const r = await bereinigeImportTasks(); tasks = r.aufgaben || []; } catch { tasks = tasks.filter(t => t.status === "wartend" || t.status === "verarbeite"); } }}>
            <i class="fa-solid fa-broom"></i> {fertige} abgeschlossene bereinigen
          </button>
        {/if}
      </div>

      <div class="tasks-list">
        {#each tasks as task (task.id)}
          <ImportStatus {task} />
        {/each}
      </div>
    {/if}
  {:else if activeTab === "gutenberg"}
    <GutenbergImport />
  {/if}
</div>

<style>
  .import-page {
    max-width: 800px;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .page-header {
    position: sticky;
    top: -1.5rem;
    z-index: 10;
    background-color: var(--color-bg-primary);
    margin: -1.5rem -1.5rem 0;
    padding: 1.5rem 1.5rem 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .tab-bar {
    display: flex;
    gap: 0.25rem;
    border-bottom: 1px solid var(--glass-border);
    padding-bottom: -1px;
  }

  .tab-btn {
    padding: 0.5rem 1rem;
    border: none;
    border-bottom: 2px solid transparent;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
  }

  .tab-btn:hover {
    color: var(--color-text-primary);
  }

  .tab-btn.active {
    color: var(--color-accent);
    border-bottom-color: var(--color-accent);
    font-weight: 600;
  }

  .error-banner {
    padding: 0.75rem 1rem;
    border: 1px solid var(--color-error);
    border-radius: 8px;
    background-color: color-mix(in srgb, var(--color-error) 10%, transparent);
    color: var(--color-error);
    font-size: 0.875rem;
  }

  .scan-actions {
    display: flex;
    gap: 0.75rem;
  }

  .action-btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    color: var(--color-text-primary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .action-btn:hover:not(:disabled) {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
  }

  .action-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .tasks-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .tasks-count {
    font-size: 0.875rem;
    color: var(--color-text-muted);
    font-weight: 600;
  }

  .clear-btn {
    font-size: 0.8125rem;
    padding: 0.375rem 0.75rem;
  }

  .tasks-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
</style>
