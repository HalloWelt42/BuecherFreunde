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
    brecheImportAb,
  } from "../lib/api/imports.js";

  let activeTab = $state("dateien");
  let tasks = $state([]);
  let laden = $state(false);
  let fehler = $state(null);
  let scanInfo = $state(null);
  let anreichern = $state(false);
  let zaehler = $state({});
  let sseConnection = $state(null);

  import { get } from "../lib/api/client.js";
  import { onMount, onDestroy } from "svelte";

  let pfade = $state({ import_dir: "", extern_dir: "" });

  onMount(async () => {
    aktualisiereStatus();
    starteSSE();
    try {
      const result = await get("/api/config/paths");
      pfade.import_dir = result.import || "";
      pfade.extern_dir = result.extern || "";
    } catch {
      // Pfade konnten nicht geladen werden
    }
  });

  onDestroy(() => {
    sseConnection?.close();
  });

  async function aktualisiereStatus() {
    try {
      const result = await holeImportStatus();
      zaehler = result.zaehler || {};
      tasks = result.aufgaben || [];
    } catch {
      // Beim ersten Laden noch keine Tasks
    }
  }

  function starteSSE() {
    sseConnection?.close();
    sseConnection = importEvents(
      (event) => {
        const d = event.data;
        if (d) {
          if (d.zaehler) zaehler = d.zaehler;
          if (d.aufgaben) tasks = d.aufgaben;
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
    scanInfo = null;
    try {
      const result = await scanneImportVerzeichnis(anreichern);
      const neueTasks = result.aufgaben || result.tasks || [];
      if (neueTasks.length > 0) {
        tasks = [...neueTasks, ...tasks];
        scanInfo = { typ: "erfolg", text: `${result.gefunden || 0} Dateien gefunden, ${neueTasks.length} neue werden importiert` };
      } else if (result.gefunden > 0) {
        scanInfo = { typ: "info", text: `${result.gefunden} Dateien gefunden -- alle bereits importiert (Duplikate)` };
      } else {
        scanInfo = { typ: "info", text: "Keine importierbaren Dateien im Verzeichnis gefunden" };
      }
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  async function abbrechen() {
    try {
      const result = await brecheImportAb();
      zaehler = result.zaehler || {};
      tasks = result.aufgaben || [];
      scanInfo = { typ: "info", text: "Wartende Aufgaben abgebrochen" };
    } catch (e) {
      fehler = e.message;
    }
  }

  async function scanExtern() {
    laden = true;
    fehler = null;
    scanInfo = null;
    try {
      const result = await scanneExternesVerzeichnis(anreichern);
      const neueTasks = result.aufgaben || result.tasks || [];
      if (neueTasks.length > 0) {
        tasks = [...neueTasks, ...tasks];
        scanInfo = { typ: "erfolg", text: `${result.gefunden || 0} Dateien gefunden, ${neueTasks.length} neue werden importiert` };
      } else if (result.gefunden > 0) {
        scanInfo = { typ: "info", text: `${result.gefunden} Dateien gefunden -- alle bereits importiert (Duplikate)` };
      } else {
        scanInfo = { typ: "info", text: "Keine importierbaren Dateien im externen Verzeichnis gefunden" };
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

    {#if scanInfo}
      <div class="scan-info" class:scan-info-erfolg={scanInfo.typ === "erfolg"}>
        <i class="fa-solid {scanInfo.typ === 'erfolg' ? 'fa-check-circle' : 'fa-info-circle'}"></i>
        <span>{scanInfo.text}</span>
      </div>
    {/if}

    {#if laden}
      <div class="scan-info scan-info-aktiv">
        <i class="fa-solid fa-spinner fa-spin"></i>
        <span>Verzeichnis wird gescannt...</span>
      </div>
    {/if}

    <div class="scan-options">
      <label class="option-check">
        <input type="checkbox" bind:checked={anreichern} />
        <span>Metadaten anreichern (Open Library) -- langsamer, holt fehlende Infos per API</span>
      </label>
    </div>

    <div class="scan-actions">
      <div class="scan-action-item">
        <button class="action-btn scan-btn" onclick={scanImport} disabled={laden}>
          <i class="fa-solid fa-folder-open"></i> Import-Verzeichnis scannen
        </button>
        {#if pfade.import_dir}
          <span class="scan-path">{pfade.import_dir}</span>
        {/if}
        <span class="scan-desc">Dateien werden beim Import verschoben und im Hash-Speicher abgelegt. Das Verzeichnis dient als Eingangskorb.</span>
      </div>
      <div class="scan-action-item">
        <button class="action-btn scan-btn" onclick={scanExtern} disabled={laden}>
          <i class="fa-solid fa-hard-drive"></i> Externes Verzeichnis scannen
        </button>
        {#if pfade.extern_dir}
          <span class="scan-path">{pfade.extern_dir}</span>
        {/if}
        <span class="scan-desc">Read-only -- Dateien werden kopiert, das Original bleibt unangetastet. Gedacht für USB-Laufwerke oder Netzlaufwerke.</span>
      </div>
    </div>

    {#if zaehler.gesamt > 0 || tasks.length > 0}
      {@const aktiv = (zaehler.wartend || 0) + (zaehler.verarbeite || 0)}
      {@const fertig = zaehler.fertig || 0}
      {@const fehlerCount = zaehler.fehler || 0}
      {@const duplikatCount = zaehler.duplikat || 0}
      {@const gesamt = zaehler.gesamt || 0}

      <div class="import-summary">
        <span class="summary-item"><strong>{gesamt}</strong> gesamt</span>
        {#if fertig > 0}<span class="summary-item summary-ok"><i class="fa-solid fa-check"></i> {fertig} fertig</span>{/if}
        {#if duplikatCount > 0}<span class="summary-item summary-dup"><i class="fa-solid fa-clone"></i> {duplikatCount} Duplikate</span>{/if}
        {#if fehlerCount > 0}<span class="summary-item summary-err"><i class="fa-solid fa-xmark"></i> {fehlerCount} Fehler</span>{/if}
        {#if aktiv > 0}<span class="summary-item summary-aktiv"><i class="fa-solid fa-spinner fa-spin"></i> {aktiv} aktiv</span>{/if}
      </div>

      <ImportProgress {tasks} />

      <div class="tasks-header">
        <span class="tasks-count">{tasks.length} angezeigte Aufgaben</span>
        <div class="tasks-actions">
          {#if aktiv > 0}
            <button class="action-btn cancel-btn" onclick={abbrechen}>
              <i class="fa-solid fa-stop"></i> Abbrechen ({zaehler.wartend || 0} wartend)
            </button>
          {/if}
          {#if fertig + fehlerCount + duplikatCount > 0}
            <button class="action-btn clear-btn" onclick={async () => { try { const r = await bereinigeImportTasks(); zaehler = r.zaehler || {}; tasks = r.aufgaben || []; } catch {} }}>
              <i class="fa-solid fa-broom"></i> Bereinigen
            </button>
          {/if}
        </div>
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

  .scan-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.625rem 1rem;
    border-radius: 8px;
    font-size: 0.8125rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    color: var(--color-text-secondary);
  }

  .scan-info-erfolg {
    border-color: var(--color-success);
    color: var(--color-success);
  }

  .scan-info-aktiv {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  .scan-options {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .option-check {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    cursor: pointer;
  }

  .option-check input[type="checkbox"] {
    accent-color: var(--color-accent);
  }

  .scan-actions {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .scan-action-item {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .scan-btn {
    width: 100%;
  }

  .scan-path {
    font-family: var(--font-mono, monospace);
    font-size: 0.75rem;
    color: var(--color-text-muted);
    padding-left: 0.25rem;
    word-break: break-all;
    user-select: all;
  }

  .scan-desc {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    line-height: 1.4;
    padding-left: 0.25rem;
    opacity: 0.7;
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

  .import-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
  }

  .summary-item {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .summary-item strong {
    color: var(--color-text-primary);
  }

  .summary-ok { color: var(--color-success); }
  .summary-dup { color: var(--color-text-muted); }
  .summary-err { color: var(--color-error); }
  .summary-aktiv { color: var(--color-accent); }

  .tasks-actions {
    display: flex;
    gap: 0.5rem;
  }

  .cancel-btn {
    color: var(--color-error);
    border-color: var(--color-error);
  }

  .cancel-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-error) 10%, transparent);
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
