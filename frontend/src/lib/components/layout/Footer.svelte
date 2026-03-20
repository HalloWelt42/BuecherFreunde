<script>
  let version = $state("...");

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

  $effect(() => {
    ladeVersion();
  });
</script>

<footer class="app-footer">
  <span>BücherFreunde v{version}</span>
</footer>

<style>
  .app-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem;
    background-color: var(--color-bg-secondary);
    border-top: 1px solid var(--color-border);
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
</style>
