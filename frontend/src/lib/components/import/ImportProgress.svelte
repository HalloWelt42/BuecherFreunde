<script>
  import ProgressBar from "../ui/ProgressBar.svelte";

  let { tasks = [] } = $props();

  let gesamtFortschritt = $derived.by(() => {
    if (tasks.length === 0) return 0;
    const sum = tasks.reduce((acc, t) => acc + (t.progress_percent || 0), 0);
    return sum / tasks.length;
  });

  let fertige = $derived(tasks.filter((t) => t.status === "fertig").length);
  let fehlerhaft = $derived(tasks.filter((t) => t.status === "fehler").length);
</script>

{#if tasks.length > 0}
  <div class="import-progress">
    <ProgressBar
      percent={gesamtFortschritt}
      label="Gesamtfortschritt: {fertige}/{tasks.length} fertig{fehlerhaft > 0 ? `, ${fehlerhaft} Fehler` : ''}"
    />
  </div>
{/if}

<style>
  .import-progress {
    padding: 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
  }
</style>
