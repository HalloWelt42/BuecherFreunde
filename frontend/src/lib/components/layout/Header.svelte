<script>
  import { ui } from "../../stores/ui.svelte.js";
  import { push } from "svelte-spa-router";

  let searchQuery = $state("");

  function onSearch(event) {
    if (event.key === "Enter" && searchQuery.trim()) {
      push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  }

  const themeIcons = { light: "\u2600", dark: "\u263D", system: "\u25D0" };
  const themeLabels = { light: "Hell", dark: "Dunkel", system: "System" };
</script>

<header class="app-header">
  <div class="header-left">
    <button
      class="sidebar-toggle"
      onclick={() => ui.toggleSidebar()}
      title="Seitenleiste"
    >
      &#9776;
    </button>
    <a href="#/" class="app-title">BuecherFreunde</a>
  </div>

  <div class="header-center">
    <input
      type="search"
      placeholder="Buecher durchsuchen..."
      class="search-input"
      bind:value={searchQuery}
      onkeydown={onSearch}
    />
  </div>

  <div class="header-right">
    <button
      class="theme-toggle"
      onclick={() => ui.cycleTheme()}
      title="Theme: {themeLabels[ui.theme]}"
    >
      {themeIcons[ui.theme]}
    </button>
  </div>
</header>

<style>
  .app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1rem;
    height: var(--header-height);
    background-color: var(--color-bg-secondary);
    border-bottom: 1px solid var(--color-border);
    gap: 1rem;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .sidebar-toggle {
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: var(--color-text-secondary);
    padding: 0.25rem;
  }

  .app-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-accent);
    text-decoration: none;
    white-space: nowrap;
  }

  .header-center {
    flex: 1;
    max-width: 600px;
  }

  .search-input {
    width: 100%;
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-family: var(--font-sans);
    font-size: 0.875rem;
  }

  .search-input:focus {
    outline: 2px solid var(--color-accent);
    outline-offset: -1px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .theme-toggle {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    cursor: pointer;
    font-size: 1.1rem;
    color: var(--color-text-secondary);
  }

  .theme-toggle:hover {
    background-color: var(--color-bg-tertiary);
  }
</style>
