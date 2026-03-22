<script>
  import ProgressBar from "../ui/ProgressBar.svelte";
  import { get, post, getToken } from "../../api/client.js";

  let backups = $state([]);
  let laden = $state(false);
  let erstellungLaeuft = $state(false);
  let meldung = $state("");

  import { onMount } from "svelte";

  onMount(() => {
    ladeBackups();
  });

  async function ladeBackups() {
    try {
      backups = await get("/api/backup/list");
    } catch {
      backups = [];
    }
  }

  async function erstelleBackup() {
    erstellungLaeuft = true;
    meldung = "";
    try {
      const result = await post("/api/backup/create");
      meldung = `Backup "${result.filename}" erstellt (${formatSize(result.size)})`;
      await ladeBackups();
    } catch (e) {
      meldung = `Fehler: ${e.message}`;
    } finally {
      erstellungLaeuft = false;
    }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
</script>

<div class="backup-panel">
  <div class="panel-header">
    <button
      class="action-btn"
      onclick={erstelleBackup}
      disabled={erstellungLaeuft}
    >
      {erstellungLaeuft ? "Erstelle..." : "Backup erstellen"}
    </button>
  </div>

  {#if meldung}
    <p class="meldung">{meldung}</p>
  {/if}

  {#if backups.length > 0}
    <div class="backup-list">
      {#each backups as backup (backup.filename)}
        <div class="backup-item">
          <div class="backup-info">
            <span class="backup-name">{backup.filename}</span>
            <span class="backup-meta">
              {formatSize(backup.size)} - {formatDate(backup.created_at)}
            </span>
          </div>
          <a
            href="/api/backup/download?filename={backup.filename}&token={encodeURIComponent(getToken())}"
            class="download-link"
          >
            Herunterladen
          </a>
        </div>
      {/each}
    </div>
  {:else}
    <p class="info">Noch keine Backups vorhanden.</p>
  {/if}
</div>

<style>
  .backup-panel {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .action-btn {
    padding: 0.5rem 1rem;
    background-color: var(--color-accent);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    cursor: pointer;
  }

  .action-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .meldung {
    font-size: 0.8125rem;
    color: var(--color-success);
  }

  .info {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .backup-list {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .backup-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--color-border);
  }

  .backup-name {
    font-size: 0.8125rem;
    font-family: var(--font-mono);
    color: var(--color-text-primary);
  }

  .backup-meta {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    display: block;
    margin-top: 0.125rem;
  }

  .download-link {
    font-size: 0.8125rem;
    color: var(--color-accent);
    text-decoration: none;
  }

  .download-link:hover {
    text-decoration: underline;
  }
</style>
