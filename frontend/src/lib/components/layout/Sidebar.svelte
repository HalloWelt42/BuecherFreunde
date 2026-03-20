<script>
  import { ui } from "../../stores/ui.svelte.js";
  import { categoriesStore } from "../../stores/categories.svelte.js";
  import { tagsStore } from "../../stores/tags.svelte.js";
  import { router } from "svelte-spa-router";
  import CategoryTree from "./CategoryTree.svelte";

  const navItems = [
    { path: "/", label: "Bibliothek", icon: "\u{1F4DA}" },
    { path: "/import", label: "Import", icon: "\u{1F4E5}" },
    { path: "/settings", label: "Einstellungen", icon: "\u2699" },
  ];

  let activeCategory = $derived.by(() => {
    const params = new URLSearchParams(router.querystring || "");
    const id = params.get("category");
    return id ? Number(id) : null;
  });

  function isActive(current, path) {
    if (path === "/") return current === "/" || current === "";
    return current.startsWith(path);
  }

  $effect(() => {
    categoriesStore.aktualisieren();
    tagsStore.aktualisieren();
  });
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
      {#if categoriesStore.laden}
        <p class="placeholder-text">Wird geladen...</p>
      {:else if categoriesStore.fehler}
        <p class="error-text">{categoriesStore.fehler}</p>
      {:else if categoriesStore.kategorien.length === 0}
        <p class="placeholder-text">Keine Kategorien vorhanden</p>
      {:else}
        <CategoryTree
          categories={categoriesStore.kategorien}
          activeId={activeCategory}
        />
      {/if}
    </div>

    <div class="sidebar-section">
      <h3 class="section-title">Tags</h3>
      {#if tagsStore.tags.length > 0}
        <div class="tag-list">
          {#each tagsStore.tags as tag (tag.id)}
            <a
              href="#/?tag={tag.id}"
              class="tag-badge"
              style="--tag-color: {tag.color || 'var(--color-accent)'}"
            >
              {tag.name}
              {#if tag.buch_anzahl > 0}
                <span class="tag-count">{tag.buch_anzahl}</span>
              {/if}
            </a>
          {/each}
        </div>
      {:else}
        <p class="placeholder-text">Keine Tags vorhanden</p>
      {/if}
    </div>

    <div class="sidebar-section">
      <h3 class="section-title">Filter</h3>
      <div class="filter-chips">
        <a href="#/?is_favorite=true" class="chip">Favoriten</a>
        <a href="#/?is_to_read=true" class="chip">Zum Lesen</a>
        <a href="#/?min_rating=4" class="chip">Top bewertet</a>
      </div>
    </div>

    <div class="sidebar-section">
      <h3 class="section-title">Format</h3>
      <div class="filter-chips">
        <a href="#/?file_format=pdf" class="chip">PDF</a>
        <a href="#/?file_format=epub" class="chip">EPUB</a>
        <a href="#/?file_format=mobi" class="chip">MOBI</a>
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

  .error-text {
    font-size: 0.8125rem;
    color: var(--color-error, #e53e3e);
  }

  .tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .tag-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.1875rem 0.5rem;
    border-radius: 999px;
    background-color: color-mix(in srgb, var(--tag-color) 15%, transparent);
    color: var(--tag-color);
    font-size: 0.75rem;
    text-decoration: none;
    transition: opacity 0.15s;
  }

  .tag-badge:hover {
    opacity: 0.8;
  }

  .tag-count {
    font-size: 0.625rem;
    opacity: 0.7;
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
    text-decoration: none;
    transition: all 0.15s;
  }

  .chip:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }
</style>
