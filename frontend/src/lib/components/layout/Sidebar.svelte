<script>
  import { ui } from "../../stores/ui.svelte.js";
  import { categoriesStore } from "../../stores/categories.svelte.js";
  import { tagsStore } from "../../stores/tags.svelte.js";
  import { route, navigate } from "../../router.svelte.js";
  import { get } from "../../api/client.js";
  import { onMount, onDestroy } from "svelte";
  import { onBooksChanged } from "../../stores/processes.svelte.js";

  let stats = $state({
    buecher_gesamt: 0, favoriten: 0, leseliste: 0,
    gelesen: 0, ungelesen: 0, buecher_mit_isbn: 0, dokumente: 0,
    weiterlesen: 0,
  });

  let version = $state("...");

  async function ladeVersion() {
    try {
      const res = await fetch("/api/config/version");
      if (res.ok) {
        const data = await res.json();
        version = data.version;
      }
    } catch {
      version = "?";
    }
  }

  // Aktive Kategorie-IDs aus URL lesen
  let activeCategories = $derived.by(() => {
    const v = new URLSearchParams(route.qs || "").get("category");
    return v ? v.split(",") : [];
  });

  let params_ = $derived(new URLSearchParams(route.qs || ""));
  let isFavorite = $derived(params_.get("is_favorite") === "true");
  let isToRead = $derived(params_.get("is_to_read") === "true");
  let isGelesen = $derived(params_.get("gelesen") === "true");
  let isUngelesen = $derived(params_.get("gelesen") === "false");
  let isBuecher = $derived(params_.get("hat_isbn") === "true");
  let isDokumente = $derived(params_.get("hat_isbn") === "false");
  let isHome = $derived(route.path === "/" || route.path === "");
  let hasNoSpecialFilter = $derived(
    !isFavorite && !isToRead && !isGelesen && !isUngelesen &&
    !isBuecher && !isDokumente && activeCategories.length === 0
  );

  function toggleCategory(catId) {
    const strId = String(catId);
    const params = new URLSearchParams(route.qs || "");
    let current = params.get("category") ? params.get("category").split(",") : [];

    if (current.includes(strId)) {
      current = current.filter((c) => c !== strId);
    } else {
      current.push(strId);
    }

    if (current.length > 0) {
      params.set("category", current.join(","));
    } else {
      params.delete("category");
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  function goFavoriten() {
    const params = new URLSearchParams(route.qs || "");
    if (params.get("is_favorite")) {
      params.delete("is_favorite");
    } else {
      params.set("is_favorite", "true");
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  function goLeseliste() {
    const params = new URLSearchParams(route.qs || "");
    if (params.get("is_to_read")) {
      params.delete("is_to_read");
    } else {
      params.set("is_to_read", "true");
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  function toggleSpecial(key, value) {
    const params = new URLSearchParams(route.qs || "");
    if (params.get(key) === value) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  async function ladeStats() {
    try {
      stats = await get("/api/config/stats");
    } catch {
      // still
    }
  }

  // Kategorien (flach)
  let cats = $derived(categoriesStore.kategorien);

  // Aktive Tag-IDs aus URL lesen
  let activeTags = $derived.by(() => {
    const v = new URLSearchParams(route.qs || "").get("tag");
    return v ? v.split(",") : [];
  });

  function toggleTag(tagId) {
    const strId = String(tagId);
    const params = new URLSearchParams(route.qs || "");
    let current = params.get("tag") ? params.get("tag").split(",") : [];

    if (current.includes(strId)) {
      current = current.filter((t) => t !== strId);
    } else {
      current.push(strId);
    }

    if (current.length > 0) {
      params.set("tag", current.join(","));
    } else {
      params.delete("tag");
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  let _unsubProcesses;

  onMount(() => {
    ladeStats();
    ladeVersion();
    categoriesStore.aktualisieren();
    tagsStore.aktualisieren();

    // Bei neuen Importen Sidebar-Zaehler aktualisieren
    _unsubProcesses = onBooksChanged(() => {
      ladeStats();
      categoriesStore.aktualisieren();
    });
  });

  onDestroy(() => {
    if (_unsubProcesses) _unsubProcesses();
  });
</script>

<aside class="sidebar" class:collapsed={!ui.sidebarOpen}>
  <!-- Navigation -->
  <nav class="sidebar-nav">
    <a
      href="/"
      class="nav-item"
      class:active={isHome && hasNoSpecialFilter}
    >
      <span class="nav-icon"><i class="fa-solid fa-layer-group"></i></span>
      <span class="nav-label">Alle</span>
      {#if stats.buecher_gesamt > 0}
        <span class="nav-count">{stats.buecher_gesamt}</span>
      {/if}
    </a>
    <button class="nav-item" class:active={isBuecher} onclick={() => toggleSpecial("hat_isbn", "true")}>
      <span class="nav-icon"><i class="fa-solid fa-book"></i></span>
      <span class="nav-label">Bücher</span>
      {#if stats.buecher_mit_isbn > 0}
        <span class="nav-count">{stats.buecher_mit_isbn}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isDokumente} onclick={() => toggleSpecial("hat_isbn", "false")}>
      <span class="nav-icon"><i class="fa-solid fa-file-lines"></i></span>
      <span class="nav-label">Dokumente</span>
      {#if stats.dokumente > 0}
        <span class="nav-count">{stats.dokumente}</span>
      {/if}
    </button>
  </nav>

  <div class="sidebar-divider"></div>

  <!-- Status -->
  <div class="section-label">Status</div>
  <nav class="sidebar-nav">
    <button class="nav-item" class:active={isGelesen} onclick={() => toggleSpecial("gelesen", "true")}>
      <span class="nav-icon"><i class="fa-solid fa-check-circle"></i></span>
      <span class="nav-label">Gelesen</span>
      {#if stats.gelesen > 0}
        <span class="nav-count">{stats.gelesen}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isUngelesen} onclick={() => toggleSpecial("gelesen", "false")}>
      <span class="nav-icon"><i class="fa-regular fa-circle"></i></span>
      <span class="nav-label">Ungelesen</span>
      {#if stats.ungelesen > 0}
        <span class="nav-count">{stats.ungelesen}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={params_.get("weiterlesen") === "true"} onclick={() => toggleSpecial("weiterlesen", "true")}>
      <span class="nav-icon"><i class="fa-solid fa-book-open-reader"></i></span>
      <span class="nav-label">Weiterlesen</span>
      {#if stats.weiterlesen > 0}
        <span class="nav-count">{stats.weiterlesen}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isFavorite} onclick={goFavoriten}>
      <span class="nav-icon">
        <i class="fa-solid fa-heart" style="color: var(--color-favorite)"></i>
      </span>
      <span class="nav-label">Favoriten</span>
      {#if stats.favoriten > 0}
        <span class="nav-count">{stats.favoriten}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isToRead} onclick={goLeseliste}>
      <span class="nav-icon">
        <i class="fa-solid fa-bookmark" style="color: var(--color-accent)"></i>
      </span>
      <span class="nav-label">Leseliste</span>
      {#if stats.leseliste > 0}
        <span class="nav-count">{stats.leseliste}</span>
      {/if}
    </button>
  </nav>

  <div class="sidebar-divider"></div>

  <!-- Kategorien -->
  <div class="section-label">Kategorien</div>
  <div class="categories-list">
    {#each cats as cat (cat.id)}
      <button
        class="cat-btn"
        class:active={activeCategories.includes(String(cat.id))}
        onclick={() => toggleCategory(cat.id)}
        title={cat.name}
      >
        {#if cat.icon}
          <i class="fa-solid {cat.icon} cat-icon" style="color: {cat.color || '#6b7280'}"></i>
        {:else if cat.color && cat.color !== '#6b7280'}
          <span class="cat-dot" style="background-color: {cat.color}"></span>
        {/if}
        <span class="cat-name">{cat.name}</span>
        {#if cat.buch_anzahl > 0}
          <span class="cat-count">{cat.buch_anzahl}</span>
        {/if}
      </button>
    {/each}
    {#if cats.length === 0 && !categoriesStore.laden}
      <div class="empty-hint">Keine Kategorien</div>
    {/if}
  </div>

  <!-- Tags -->
  {#if tagsStore.tags.length > 0}
    <div class="sidebar-divider"></div>
    <div class="section-label">Tags</div>
    <div class="tags-list">
      {#each tagsStore.tags as tag (tag.id)}
        <button
          class="tag-btn"
          class:active={activeTags.includes(String(tag.id))}
          onclick={() => toggleTag(tag.id)}
          title={tag.name}
        >
          <span class="tag-dot" style="background-color: {tag.color}"></span>
          <span class="tag-name">{tag.name}</span>
          {#if tag.buch_anzahl > 0}
            <span class="tag-count">{tag.buch_anzahl}</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}

  <div class="sidebar-divider"></div>

  <!-- Verwalten -->
  <div class="section-label">Verwalten</div>
  <nav class="sidebar-nav">
    <a
      href="/import"
      class="nav-item"
      class:active={route.path === "/import"}
    >
      <span class="nav-icon"><i class="fa-solid fa-file-import"></i></span>
      <span class="nav-label">Import</span>
    </a>
    <a
      href="/settings"
      class="nav-item"
      class:active={route.path === "/settings"}
    >
      <span class="nav-icon"><i class="fa-solid fa-gear"></i></span>
      <span class="nav-label">Einstellungen</span>
    </a>
  </nav>

  <!-- Spacer + Version -->
  <div class="sidebar-spacer"></div>
  <div class="sidebar-version">BücherFreunde v{version}</div>
</aside>

<style>
  .sidebar {
    background-color: var(--color-bg-secondary);
    border-right: 1px solid var(--color-border);
    padding: 0.75rem;
    overflow-y: auto;
    overflow-x: hidden;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    height: 100%;
    transition: opacity 0.2s ease;
  }

  .sidebar.collapsed {
    opacity: 0;
    pointer-events: none;
  }

  .sidebar-divider {
    height: 1px;
    background: var(--color-border);
    margin: 0.375rem 0;
  }

  .section-label {
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    padding: 0.375rem 0.75rem 0.125rem;
  }

  .sidebar-nav {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    color: var(--color-text-secondary);
    text-decoration: none;
    font-size: 0.8125rem;
    font-weight: 500;
    transition: background-color 0.12s, color 0.12s;
    border: none;
    background: none;
    width: 100%;
    text-align: left;
    cursor: pointer;
  }

  .nav-item:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .nav-item.active {
    background-color: var(--color-accent);
    color: #fff;
  }

  .nav-item.active .nav-icon i {
    color: #fff !important;
  }

  .nav-item.active .nav-count {
    background-color: rgba(255, 255, 255, 0.2);
    color: #fff;
  }

  .nav-icon {
    font-size: 0.875rem;
    width: 1.25rem;
    text-align: center;
    flex-shrink: 0;
  }

  .nav-label {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .nav-count {
    font-size: 0.625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    padding: 0.0625rem 0.375rem;
    border-radius: 999px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  /* Kategorien */
  .categories-list {
    display: flex;
    flex-direction: column;
    gap: 1px;
    max-height: 300px;
    overflow-y: auto;
  }

  .cat-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3125rem 0.5rem;
    border: none;
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: background-color 0.1s, color 0.1s;
    width: 100%;
  }

  .cat-btn:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .cat-btn.active {
    background-color: var(--color-accent-light);
    color: var(--color-accent);
    font-weight: 600;
  }

  .cat-icon {
    font-size: 0.6875rem;
    flex-shrink: 0;
    width: 0.875rem;
    text-align: center;
  }

  .cat-dot {
    width: 7px;
    height: 7px;
    border-radius: 3px;
    flex-shrink: 0;
  }

  .cat-btn.active .cat-icon {
    color: var(--color-accent) !important;
  }

  .cat-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .cat-count {
    font-size: 0.5625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    padding: 0.0625rem 0.3125rem;
    border-radius: 999px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .cat-btn.active .cat-count {
    background-color: var(--color-accent);
    color: #fff;
  }

  .empty-hint {
    padding: 0.5rem 0.75rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Tags */
  .tags-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    padding: 0 0.375rem;
  }

  .tag-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.1875rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.6875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.1s;
    white-space: nowrap;
  }

  .tag-btn:hover {
    border-color: var(--color-text-muted);
    color: var(--color-text-primary);
  }

  .tag-btn.active {
    border-color: var(--color-accent);
    background-color: var(--color-accent-light);
    color: var(--color-accent);
    font-weight: 600;
  }

  .tag-dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .tag-name {
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 8rem;
  }

  .tag-count {
    font-size: 0.5625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .tag-btn.active .tag-count {
    color: var(--color-accent);
  }

  /* Spacer + Version */
  .sidebar-spacer {
    flex: 1;
  }

  .sidebar-version {
    padding: 0.5rem 0.75rem;
    font-size: 0.625rem;
    color: var(--color-text-muted);
    text-align: center;
    opacity: 0.6;
  }
</style>
