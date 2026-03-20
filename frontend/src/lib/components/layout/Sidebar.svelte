<script>
  import { ui } from "../../stores/ui.svelte.js";
  import { router } from "svelte-spa-router";

  const navItems = [
    { path: "/", label: "Bibliothek", icon: "\u{1F4DA}" },
    { path: "/import", label: "Import", icon: "\u{1F4E5}" },
    { path: "/settings", label: "Einstellungen", icon: "\u2699" },
  ];

  function isActive(current, path) {
    if (path === "/") return current === "/" || current === "";
    return current.startsWith(path);
  }
</script>

{#if ui.sidebarOpen}
  <aside class="sidebar">
    <nav class="sidebar-nav">
      {#each navItems as item (item.path)}
        <a
          href="#{item.path}"
          class="nav-item"
          class:active={isActive(router.location, item.path)}
        >
          <span class="nav-icon">{item.icon}</span>
          <span class="nav-label">{item.label}</span>
        </a>
      {/each}
    </nav>

    <div class="sidebar-section">
      <h3 class="section-title">Kategorien</h3>
      <p class="placeholder-text">Kategorien werden geladen...</p>
    </div>

    <div class="sidebar-section">
      <h3 class="section-title">Sammlungen</h3>
      <p class="placeholder-text">Keine Sammlungen vorhanden</p>
    </div>

    <div class="sidebar-section">
      <h3 class="section-title">Filter</h3>
      <div class="filter-chips">
        <button class="chip">Favoriten</button>
        <button class="chip">Zum Lesen</button>
      </div>
    </div>
  </aside>
{/if}

<style>
  .sidebar {
    background-color: var(--color-bg-secondary);
    border-right: 1px solid var(--color-border);
    padding: 1rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .sidebar-nav {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    color: var(--color-text-secondary);
    text-decoration: none;
    font-size: 0.875rem;
    transition: background-color 0.15s;
  }

  .nav-item:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .nav-item.active {
    background-color: var(--color-accent);
    color: #fff;
  }

  .nav-icon {
    font-size: 1.1rem;
    width: 1.5rem;
    text-align: center;
  }

  .sidebar-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .section-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .placeholder-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .filter-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .chip {
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .chip:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }
</style>
