<script>
  let { value = "", onchange = () => {} } = $props();

  let open = $state(false);
  let search = $state("");

  const icons = [
    "fa-book", "fa-book-open", "fa-book-bookmark", "fa-book-atlas",
    "fa-file", "fa-file-lines", "fa-file-pdf", "fa-file-code",
    "fa-scroll", "fa-newspaper", "fa-bookmark",
    "fa-graduation-cap", "fa-microscope", "fa-flask", "fa-atom",
    "fa-brain", "fa-lightbulb", "fa-chalkboard", "fa-school",
    "fa-laptop-code", "fa-microchip", "fa-robot", "fa-code",
    "fa-database", "fa-server", "fa-network-wired", "fa-terminal",
    "fa-folder", "fa-folder-open", "fa-tag", "fa-tags",
    "fa-layer-group", "fa-boxes-stacked", "fa-sitemap", "fa-list",
    "fa-globe", "fa-earth-americas", "fa-leaf", "fa-tree",
    "fa-mountain-sun", "fa-water", "fa-sun", "fa-moon",
    "fa-user", "fa-users", "fa-children", "fa-people-group",
    "fa-handshake", "fa-comments", "fa-message", "fa-heart",
    "fa-palette", "fa-paintbrush", "fa-camera", "fa-film",
    "fa-music", "fa-guitar", "fa-masks-theater", "fa-pen-fancy",
    "fa-futbol", "fa-dumbbell", "fa-bicycle", "fa-chess",
    "fa-gamepad", "fa-puzzle-piece", "fa-dice", "fa-trophy",
    "fa-heart-pulse", "fa-stethoscope", "fa-pills", "fa-hospital",
    "fa-scale-balanced", "fa-landmark", "fa-building-columns", "fa-chart-line",
    "fa-coins", "fa-briefcase", "fa-gavel", "fa-receipt",
    "fa-cross", "fa-star-and-crescent", "fa-om", "fa-yin-yang",
    "fa-dove", "fa-pray", "fa-place-of-worship", "fa-church",
    "fa-plane", "fa-ship", "fa-car", "fa-train",
    "fa-map", "fa-compass", "fa-route", "fa-location-dot",
    "fa-utensils", "fa-mug-hot", "fa-wine-glass", "fa-apple-whole",
    "fa-star", "fa-fire", "fa-bolt", "fa-shield",
    "fa-crown", "fa-gem", "fa-key", "fa-lock",
    "fa-wand-magic-sparkles", "fa-hat-wizard", "fa-dragon", "fa-ghost",
  ];

  let filtered = $derived(
    search ? icons.filter((i) => i.includes(search.toLowerCase())) : icons
  );

  function pick(icon) {
    onchange(icon);
    open = false;
    search = "";
  }

  function remove() {
    onchange("");
    open = false;
  }
</script>

<div class="ip-wrap">
  <button class="ip-trigger" onclick={() => (open = !open)}>
    {#if value}
      <i class="fa-solid {value} ip-icon"></i>
      <span class="ip-name">{value.replace("fa-", "")}</span>
    {:else}
      <i class="fa-solid fa-icons ip-placeholder"></i>
      <span class="ip-none">Kein Icon</span>
    {/if}
    <i class="fa-solid fa-chevron-down ip-arrow" class:open></i>
  </button>

  {#if open}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="ip-backdrop" onclick={() => { open = false; search = ""; }} onkeydown></div>
    <div class="ip-popover">
      <div class="ip-search">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input
          type="text"
          placeholder="Suchen... ({icons.length})"
          bind:value={search}
        />
        {#if value}
          <button class="ip-remove" onclick={remove} title="Entfernen">
            <i class="fa-solid fa-xmark"></i>
          </button>
        {/if}
      </div>
      <div class="ip-grid">
        {#each filtered as icon (icon)}
          <button
            class="ip-btn"
            class:selected={value === icon}
            onclick={() => pick(icon)}
            title={icon}
          >
            <i class="fa-solid {icon}"></i>
          </button>
        {/each}
        {#if filtered.length === 0}
          <span class="ip-empty">Nichts gefunden</span>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .ip-wrap {
    position: relative;
    display: inline-flex;
  }

  .ip-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: border-color 0.1s;
  }

  .ip-trigger:hover {
    border-color: var(--color-accent);
  }

  .ip-icon {
    font-size: 0.8125rem;
    color: var(--color-accent);
  }

  .ip-name {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
  }

  .ip-placeholder {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .ip-none {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .ip-arrow {
    font-size: 0.5rem;
    transition: transform 0.15s;
    color: var(--color-text-muted);
  }

  .ip-arrow.open {
    transform: rotate(180deg);
  }

  .ip-backdrop {
    position: fixed;
    inset: 0;
    z-index: 99;
  }

  .ip-popover {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 100;
    width: 280px;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-secondary);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .ip-search {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.375rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background-color: var(--color-bg-primary);
    font-size: 0.625rem;
    color: var(--color-text-muted);
  }

  .ip-search input {
    flex: 1;
    border: none;
    background: none;
    color: var(--color-text-primary);
    font-size: 0.6875rem;
    font-family: var(--font-sans);
    outline: none;
  }

  .ip-search input::placeholder {
    color: var(--color-text-muted);
  }

  .ip-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    border: none;
    border-radius: 3px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.5rem;
    cursor: pointer;
  }

  .ip-remove:hover {
    color: var(--color-error);
  }

  .ip-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 2px;
    max-height: 200px;
    overflow-y: auto;
  }

  .ip-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    border: 1px solid transparent;
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
    transition: all 0.08s;
    padding: 0;
  }

  .ip-btn:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .ip-btn.selected {
    background-color: var(--color-accent-light);
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .ip-empty {
    grid-column: 1 / -1;
    text-align: center;
    padding: 1rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
</style>
