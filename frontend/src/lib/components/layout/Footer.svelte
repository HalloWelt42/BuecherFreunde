<script>
  import { onMount, onDestroy } from "svelte";
  import {
    processes,
    getProcessStats,
    startPolling,
    stopPolling,
    toggleExpanded,
  } from "../../stores/processes.svelte.js";

  let version = $state("...");

  let stats = $derived(getProcessStats());
  let hatProzesse = $derived(processes.importTasks.length > 0);
  let istAktiv = $derived(stats.aktiv > 0);

  async function ladeVersion() {
    try {
      const res = await fetch("/api/config/version");
      if (res.ok) {
        const data = await res.json();
        version = data.version;
      }
    } catch {
      version = "offline";
    }
  }

  onMount(() => {
    ladeVersion();
    startPolling();
  });

  onDestroy(() => {
    stopPolling();
  });
</script>

<footer class="app-footer" class:has-activity={istAktiv}>
  <!-- Prozessleiste (nur sichtbar wenn Prozesse existieren) -->
  {#if hatProzesse}
    <button class="process-bar" onclick={toggleExpanded} class:active={istAktiv}>
      <div class="process-summary">
        {#if istAktiv}
          <i class="fa-solid fa-spinner fa-spin process-icon"></i>
          <span class="process-text">
            {stats.aktuell?.filename
              ? stats.aktuell.filename.length > 30
                ? stats.aktuell.filename.slice(0, 27) + "..."
                : stats.aktuell.filename
              : "Verarbeite..."}
          </span>
          <span class="process-count">{stats.fertig}/{stats.gesamt}</span>
          <div class="mini-progress">
            <div class="mini-progress-fill" style="width: {stats.prozent}%"></div>
          </div>
          <span class="process-pct">{stats.prozent}%</span>
        {:else}
          <i class="fa-solid fa-check-circle process-icon done"></i>
          <span class="process-text">
            {stats.fertig} importiert
            {#if stats.fehler > 0}
              <span class="error-count">{stats.fehler} Fehler</span>
            {/if}
          </span>
        {/if}
        <i
          class="fa-solid {processes.expanded ? 'fa-chevron-down' : 'fa-chevron-up'} expand-icon"
        ></i>
      </div>
    </button>

    <!-- Aufgeklappte Details -->
    {#if processes.expanded}
      <div class="process-details">
        <div class="details-header">
          <span class="details-title">Hintergrundprozesse</span>
          <span class="details-stats">
            {stats.fertig} fertig
            {#if stats.aktiv > 0} / {stats.aktiv} aktiv{/if}
            {#if stats.fehler > 0} / <span class="err">{stats.fehler} Fehler</span>{/if}
          </span>
        </div>
        <div class="details-list">
          {#each processes.importTasks.filter((t) => t.status === "verarbeite") as task (task.id)}
            <div class="detail-row verarbeite">
              <i class="fa-solid fa-spinner fa-spin row-icon"></i>
              <span class="row-name" title={task.filename}>{task.filename}</span>
              <span class="row-step">{task.current_step}</span>
              <div class="row-progress">
                <div class="row-progress-fill" style="width: {task.progress_percent}%"></div>
              </div>
              <span class="row-pct">{task.progress_percent}%</span>
            </div>
          {/each}
          {#each processes.importTasks
            .filter((t) => t.status === "fehler")
            .slice(0, 5) as task (task.id)}
            <div class="detail-row fehler">
              <i class="fa-solid fa-triangle-exclamation row-icon"></i>
              <span class="row-name" title={task.filename}>{task.filename}</span>
              <span class="row-error" title={task.error}>{task.error}</span>
            </div>
          {/each}
          {#each processes.importTasks
            .filter((t) => t.status === "wartend")
            .slice(0, 3) as task (task.id)}
            <div class="detail-row wartend">
              <i class="fa-solid fa-clock row-icon"></i>
              <span class="row-name" title={task.filename}>{task.filename}</span>
              <span class="row-step">Wartend</span>
            </div>
          {/each}
          {#if processes.importTasks.filter((t) => t.status === "wartend").length > 3}
            <div class="detail-row more">
              <span class="row-more">
                + {processes.importTasks.filter((t) => t.status === "wartend").length - 3} weitere
                wartend
              </span>
            </div>
          {/if}
          {#each processes.importTasks
            .filter((t) => t.status === "fertig")
            .slice(-3)
            .reverse() as task (task.id)}
            <div class="detail-row fertig">
              <i class="fa-solid fa-check row-icon"></i>
              <span class="row-name" title={task.filename}>{task.filename}</span>
              {#if task.book_id}
                <a href="/book/{task.book_id}" class="row-link">Anzeigen</a>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  <!-- Version ganz rechts -->
  <span class="version-tag">BücherFreunde v{version}</span>
</footer>

<style>
  .app-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 50;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    pointer-events: none;
  }

  .app-footer.has-activity {
    pointer-events: auto;
  }

  /* Version-Tag rechts unten */
  .version-tag {
    position: fixed;
    bottom: 0;
    right: 0;
    padding: 0.25rem 0.75rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    pointer-events: none;
  }

  /* Prozessleiste */
  .process-bar {
    display: flex;
    align-items: center;
    margin-left: var(--sidebar-width);
    padding: 0.3125rem 0.75rem;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    cursor: pointer;
    pointer-events: auto;
    transition: all 0.15s;
    max-width: 600px;
  }

  .process-bar:hover {
    background-color: var(--color-bg-tertiary);
  }

  .process-bar.active {
    border-color: var(--color-accent);
    border-bottom: none;
  }

  .process-summary {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
    width: 100%;
  }

  .process-icon {
    font-size: 0.625rem;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .process-icon.done {
    color: var(--color-success);
  }

  .process-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 250px;
  }

  .error-count {
    color: var(--color-error);
    font-weight: 600;
  }

  .process-count {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .mini-progress {
    width: 60px;
    height: 4px;
    background-color: var(--color-bg-primary);
    border-radius: 2px;
    overflow: hidden;
    flex-shrink: 0;
  }

  .mini-progress-fill {
    height: 100%;
    background-color: var(--color-accent);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .process-pct {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: var(--color-text-muted);
    min-width: 28px;
    text-align: right;
    flex-shrink: 0;
  }

  .expand-icon {
    font-size: 0.5rem;
    color: var(--color-text-muted);
    margin-left: 0.25rem;
    flex-shrink: 0;
  }

  /* Aufgeklappte Details */
  .process-details {
    position: fixed;
    bottom: 28px;
    left: var(--sidebar-width);
    width: min(600px, calc(100vw - var(--sidebar-width) - 2rem));
    max-height: 300px;
    overflow-y: auto;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px 8px 0 0;
    pointer-events: auto;
    box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.15);
  }

  .details-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--color-border);
    position: sticky;
    top: 0;
    background-color: var(--color-bg-secondary);
    z-index: 1;
  }

  .details-title {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .details-stats {
    font-size: 0.625rem;
    color: var(--color-text-muted);
  }

  .details-stats .err {
    color: var(--color-error);
  }

  .details-list {
    display: flex;
    flex-direction: column;
  }

  .detail-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    border-bottom: 1px solid var(--color-border);
    font-size: 0.6875rem;
  }

  .detail-row:last-child {
    border-bottom: none;
  }

  .row-icon {
    font-size: 0.5625rem;
    width: 0.75rem;
    text-align: center;
    flex-shrink: 0;
  }

  .detail-row.verarbeite .row-icon {
    color: var(--color-accent);
  }

  .detail-row.fehler .row-icon {
    color: var(--color-error);
  }

  .detail-row.wartend .row-icon {
    color: var(--color-text-muted);
  }

  .detail-row.fertig .row-icon {
    color: var(--color-success);
  }

  .row-name {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--color-text-primary);
    max-width: 250px;
  }

  .row-step {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .row-error {
    font-size: 0.625rem;
    color: var(--color-error);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }

  .row-progress {
    width: 50px;
    height: 3px;
    background-color: var(--color-bg-primary);
    border-radius: 2px;
    overflow: hidden;
    flex-shrink: 0;
  }

  .row-progress-fill {
    height: 100%;
    background-color: var(--color-accent);
    border-radius: 2px;
    transition: width 0.3s;
  }

  .row-pct {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    min-width: 24px;
    text-align: right;
    flex-shrink: 0;
  }

  .row-link {
    font-size: 0.625rem;
    color: var(--color-accent);
    text-decoration: none;
    white-space: nowrap;
  }

  .row-link:hover {
    text-decoration: underline;
  }

  .row-more {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    font-style: italic;
    padding-left: 1.25rem;
  }

  .detail-row.more {
    padding: 0.25rem 0.75rem;
  }
</style>
