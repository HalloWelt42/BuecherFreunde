<script>
  import ProgressBar from "../ui/ProgressBar.svelte";

  let { task } = $props();

  const statusConfig = {
    wartend: { label: "Wartend", color: "var(--color-text-muted)", icon: "\u23F3" },
    verarbeite: { label: "Wird verarbeitet", color: "var(--color-accent)", icon: "\u2699" },
    fertig: { label: "Fertig", color: "var(--color-success)", icon: "\u2713" },
    fehler: { label: "Fehler", color: "var(--color-error)", icon: "\u2717" },
  };

  let config = $derived(statusConfig[task.status] || statusConfig.wartend);
</script>

<div class="import-task" class:error={task.status === "fehler"}>
  <div class="task-header">
    <span class="task-icon">{config.icon}</span>
    <span class="task-filename" title={task.filename}>{task.filename}</span>
    <span class="task-status" style="color: {config.color}">
      {config.label}
    </span>
  </div>

  {#if task.status === "verarbeite"}
    <ProgressBar
      percent={task.progress_percent}
      label={task.current_step || ""}
      color={config.color}
    />
  {/if}

  {#if task.status === "fehler" && task.error}
    <p class="error-msg">{task.error}</p>
  {/if}

  {#if task.status === "fertig" && task.book_id}
    <a href="/book/{task.book_id}" class="book-link">Buch anzeigen</a>
  {/if}
</div>

<style>
  .import-task {
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .import-task.error {
    border-color: var(--color-error);
    background-color: color-mix(in srgb, var(--color-error) 5%, transparent);
  }

  .task-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .task-icon {
    font-size: 0.875rem;
  }

  .task-filename {
    flex: 1;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .task-status {
    font-size: 0.75rem;
    font-weight: 600;
  }

  .error-msg {
    font-size: 0.8125rem;
    color: var(--color-error);
  }

  .book-link {
    font-size: 0.8125rem;
    color: var(--color-accent);
    text-decoration: none;
  }

  .book-link:hover {
    text-decoration: underline;
  }
</style>
