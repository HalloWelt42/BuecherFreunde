<script>
  let { value = "#6b7280", onchange = () => {} } = $props();

  let open = $state(false);

  const colors = [
    "#ef4444", "#f43f5e", "#ec4899", "#d946ef",
    "#a855f7", "#8b5cf6", "#6366f1", "#3b82f6",
    "#0ea5e9", "#06b6d4", "#14b8a6", "#10b981",
    "#22c55e", "#84cc16", "#eab308", "#f59e0b",
    "#f97316", "#fb923c", "#78716c", "#a8a29e",
    "#6b7280", "#9ca3af", "#374151", "#111827",
  ];

  function pick(color) {
    onchange(color);
    open = false;
  }
</script>

<div class="cp-wrap">
  <button class="cp-trigger" onclick={() => (open = !open)}>
    <span class="cp-dot" style="background-color: {value}"></span>
    <span class="cp-hex">{value}</span>
    <i class="fa-solid fa-chevron-down cp-arrow" class:open></i>
  </button>

  {#if open}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="cp-backdrop" onclick={() => (open = false)} onkeydown={() => {}}></div>
    <div class="cp-popover">
      <div class="cp-grid">
        {#each colors as color (color)}
          <button
            class="cp-swatch"
            class:selected={value === color}
            style="background-color: {color}"
            onclick={() => pick(color)}
          >
            {#if value === color}<i class="fa-solid fa-check"></i>{/if}
          </button>
        {/each}
      </div>
      <div class="cp-custom">
        <input
          type="color"
          class="cp-input"
          value={value}
          onchange={(e) => pick(e.target.value)}
        />
        <span class="cp-label">Eigene Farbe</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .cp-wrap {
    position: relative;
    display: inline-flex;
  }

  .cp-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: border-color 0.1s;
  }

  .cp-trigger:hover {
    border-color: var(--color-accent);
  }

  .cp-dot {
    width: 14px;
    height: 14px;
    border-radius: 4px;
    flex-shrink: 0;
    border: 1px solid rgba(0,0,0,0.1);
  }

  .cp-hex {
    font-size: 0.6875rem;
  }

  .cp-arrow {
    font-size: 0.5rem;
    transition: transform 0.15s;
    color: var(--color-text-muted);
  }

  .cp-arrow.open {
    transform: rotate(180deg);
  }

  .cp-backdrop {
    position: fixed;
    inset: 0;
    z-index: 99;
  }

  .cp-popover {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 100;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-secondary);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .cp-grid {
    display: grid;
    grid-template-columns: repeat(8, 24px);
    gap: 3px;
  }

  .cp-swatch {
    width: 24px;
    height: 24px;
    border: 2px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 0.5rem;
    transition: transform 0.1s;
    padding: 0;
  }

  .cp-swatch:hover {
    transform: scale(1.2);
    z-index: 1;
  }

  .cp-swatch.selected {
    border-color: var(--color-text-primary);
  }

  .cp-custom {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding-top: 0.25rem;
    border-top: 1px solid var(--color-border);
  }

  .cp-input {
    width: 24px;
    height: 24px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    background: none;
  }

  .cp-input::-webkit-color-swatch-wrapper {
    padding: 2px;
  }

  .cp-input::-webkit-color-swatch {
    border: none;
    border-radius: 2px;
  }

  .cp-label {
    font-size: 0.625rem;
    color: var(--color-text-muted);
  }
</style>
