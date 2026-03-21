<script>
  import { ui } from "../../stores/ui.svelte.js";
  import SearchBar from "../search/SearchBar.svelte";

  const themeIcons = { light: "fa-sun", dark: "fa-moon", system: "fa-circle-half-stroke" };
  const themeLabels = { light: "Hell", dark: "Dunkel", system: "System" };
</script>

<header class="app-header">
  <div class="header-left">
    <button
      class="header-btn sidebar-toggle"
      onclick={() => ui.toggleSidebar()}
      title="Seitenleiste {ui.sidebarOpen ? 'einklappen' : 'ausklappen'}"
    >
      <i class="fa-solid {ui.sidebarOpen ? 'fa-bars-staggered' : 'fa-bars'}"></i>
    </button>
    <a href="/" class="app-brand">
      <i class="fa-solid fa-book-open brand-icon"></i>
      <span class="brand-text">BücherFreunde</span>
    </a>
  </div>

  <div class="header-center">
    <SearchBar />
  </div>

  <div class="header-right">
    <a href="/import" class="header-btn" title="Import">
      <i class="fa-solid fa-file-import"></i>
    </a>
    <button
      class="header-btn"
      onclick={() => ui.cycleTheme()}
      title="Theme: {themeLabels[ui.theme]}"
    >
      <i class="fa-solid {themeIcons[ui.theme]}"></i>
    </button>
    <a href="/settings" class="header-btn" title="Einstellungen">
      <i class="fa-solid fa-gear"></i>
    </a>
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
    flex-shrink: 0;
  }

  .header-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: none;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    text-decoration: none;
    transition: background-color 0.12s, color 0.12s, border-color 0.12s;
  }

  .header-btn:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
    border-color: var(--color-border);
  }

  .app-brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
    white-space: nowrap;
  }

  .brand-icon {
    font-size: 1rem;
    color: var(--color-accent);
  }

  .brand-text {
    font-size: 0.9375rem;
    font-weight: 700;
    color: var(--color-text-primary);
    letter-spacing: -0.01em;
  }

  .header-center {
    flex: 1;
    max-width: 600px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-shrink: 0;
  }
</style>
