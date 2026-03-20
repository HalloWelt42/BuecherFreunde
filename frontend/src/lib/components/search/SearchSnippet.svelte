<script>
  let { snippet = "" } = $props();
</script>

<p class="snippet">{@html snippet}</p>

<style>
  .snippet {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .snippet :global(mark) {
    background-color: var(--color-warning);
    color: var(--color-text-primary);
    padding: 0 2px;
    border-radius: 2px;
  }
</style>
