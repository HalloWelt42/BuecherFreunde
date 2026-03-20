<script>
  import { ui } from "../../stores/ui.svelte.js";
  import SearchBar from "../search/SearchBar.svelte";

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
    <a href="#/" class="app-title">BücherFreunde</a>
  </div>

  <div class="header-center">
    <SearchBar />
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
