<script>
  let { percent = 0, label = "", color = "var(--color-accent)" } = $props();
</script>

<div class="progress">
  {#if label}
    <div class="progress-header">
      <span class="progress-label">{label}</span>
      <span class="progress-value">{Math.round(percent)}%</span>
    </div>
  {/if}
  <div class="progress-track">
    <div
      class="progress-fill"
      style="width: {Math.min(percent, 100)}%; background-color: {color}"
    ></div>
  </div>
</div>

<style>
  .progress {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
  }

  .progress-label {
    color: var(--color-text-secondary);
  }

  .progress-value {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
  }

  .progress-track {
    height: 6px;
    background-color: var(--color-bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease;
  }
</style>
