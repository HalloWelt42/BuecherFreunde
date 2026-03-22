<script>
  import { ui } from "../../stores/ui.svelte.js";
  import { categoriesStore } from "../../stores/categories.svelte.js";
  import { sammlungenStore } from "../../stores/tags.svelte.js";
  import { route, navigate } from "../../router.svelte.js";
  import { get, getToken } from "../../api/client.js";
  import { onMount, onDestroy } from "svelte";
  import { onBooksChanged } from "../../stores/processes.svelte.js";

  let stats = $state({
    buecher_gesamt: 0, favoriten: 0, leseliste: 0,
    gelesen: 0, ungelesen: 0, buecher_mit_isbn: 0, dokumente: 0,
    weiterlesen: 0, autoren: 0,
  });

  let version = $state("...");
  let updateVerfuegbar = $state(false);
  let remoteVersion = $state("");

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
    // Update-Check im Hintergrund
    pruefeUpdate();
  }

  async function pruefeUpdate() {
    try {
      const token = getToken();
      const res = await fetch("/api/config/update-check", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        updateVerfuegbar = data.update_verfuegbar || false;
        remoteVersion = data.remote_version || "";
      }
    } catch {}
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
  let isLabels = $derived(params_.get("hat_highlights") === "true");
  let isHome = $derived(route.path === "/" || route.path === "");
  let hasNoSpecialFilter = $derived(
    !isFavorite && !isToRead && !isGelesen && !isUngelesen &&
    !isBuecher && !isDokumente && !isLabels && activeCategories.length === 0
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

  // Nur Spezialkategorien in der Sidebar
  let cats = $derived(categoriesStore.kategorien.filter(c => c.spezial));

  // Aktive Sammlung aus URL lesen
  let activeSammlung = $derived(new URLSearchParams(route.qs || "").get("sammlung"));

  function toggleSammlung(sammlungId) {
    const params = new URLSearchParams(route.qs || "");
    if (params.get("sammlung") === String(sammlungId)) {
      params.delete("sammlung");
    } else {
      params.set("sammlung", String(sammlungId));
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  let _unsubProcesses;

  onMount(() => {
    ladeStats();
    ladeVersion();
    categoriesStore.aktualisieren();
    sammlungenStore.aktualisieren();

    // Bei neuen Importen Sidebar-Zaehler aktualisieren
    _unsubProcesses = onBooksChanged(() => {
      ladeStats();
      categoriesStore.aktualisieren();
    });
  });

  onDestroy(() => {
    if (_unsubProcesses) _unsubProcesses();
  });

  // Schnellnotiz-Wörter aus localStorage zählen
  let schnellnotizVersion = $state(0);
  let schnellnotizWoerter = $derived.by(() => {
    const _ = ui.scratchPadOpen;
    const __ = schnellnotizVersion;
    const text = localStorage.getItem("bf-schnellnotiz") || "";
    if (!text.trim()) return 0;
    return text.trim().split(/\s+/).length;
  });

  $effect(() => {
    function onUpdate() { schnellnotizVersion++; }
    window.addEventListener("schnellnotiz-update", onUpdate);
    return () => window.removeEventListener("schnellnotiz-update", onUpdate);
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
    <button class="nav-item" class:active={isBuecher} onclick={() => toggleSpecial("hat_isbn", "true")}
      title="Nur Bücher mit ISBN anzeigen"
    >
      <span class="nav-icon"><i class="fa-solid fa-book"></i></span>
      <span class="nav-label">Bücher</span>
      {#if stats.buecher_mit_isbn > 0}
        <span class="nav-count">{stats.buecher_mit_isbn}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isDokumente} onclick={() => toggleSpecial("hat_isbn", "false")}
      title="Dateien ohne ISBN - PDFs, Dokumente, Skripte"
    >
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
    <button class="nav-item gelesen-toggle" class:active={isGelesen || isUngelesen}
      title="Klicken zum Umschalten: Alle -> Gelesen -> Ungelesen"
      onclick={() => {
        if (!isGelesen && !isUngelesen) toggleSpecial("gelesen", "true");
        else if (isGelesen) { const p = new URLSearchParams(route.qs || ""); p.set("gelesen", "false"); navigate(p.toString() ? `/?${p.toString()}` : "/"); }
        else toggleSpecial("gelesen", "false");
      }}
    >
      <span class="nav-icon">
        <i class="fa-solid fa-check-circle"></i>
      </span>
      <span class="nav-label">
        <span class="gelesen-label" class:gelesen-active={isGelesen} class:gelesen-dim={isUngelesen}>Gelesen</span>
        <span class="gelesen-sep">/</span>
        <span class="gelesen-label" class:gelesen-active={isUngelesen} class:gelesen-dim={isGelesen}>Ungelesen</span>
      </span>
      <span class="nav-count gelesen-counts">
        <span class="gelesen-label" class:gelesen-active={isGelesen} class:gelesen-dim={isUngelesen}>{stats.gelesen}</span>
        <span class="gelesen-sep">/</span>
        <span class="gelesen-label" class:gelesen-active={isUngelesen} class:gelesen-dim={isGelesen}>{stats.ungelesen}</span>
      </span>
    </button>
    <button class="nav-item" class:active={params_.get("weiterlesen") === "true"} onclick={() => toggleSpecial("weiterlesen", "true")}
      title="Bücher mit gespeicherter Leseposition"
    >
      <span class="nav-icon"><i class="fa-solid fa-bookmark"></i></span>
      <span class="nav-label">Weiterlesen</span>
      {#if stats.weiterlesen > 0}
        <span class="nav-count">{stats.weiterlesen}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isFavorite} onclick={goFavoriten}
      title="Deine Lieblingsbücher"
    >
      <span class="nav-icon">
        <i class="fa-solid fa-heart" style="color: var(--color-favorite)"></i>
      </span>
      <span class="nav-label">Favoriten</span>
      {#if stats.favoriten > 0}
        <span class="nav-count">{stats.favoriten}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isToRead} onclick={goLeseliste}
      title="Bücher, die du dir zum Lesen vorgemerkt hast"
    >
      <span class="nav-icon">
        <i class="fa-solid fa-book-open"></i>
      </span>
      <span class="nav-label">Lesesofa</span>
      {#if stats.leseliste > 0}
        <span class="nav-count">{stats.leseliste}</span>
      {/if}
    </button>
    <button class="nav-item" class:active={isLabels} onclick={() => toggleSpecial("hat_highlights", "true")}
      title="Bücher mit Labels und Markierungen"
    >
      <span class="nav-icon"><i class="fa-solid fa-tags"></i></span>
      <span class="nav-label">Labels</span>
      {#if stats.mit_highlights > 0}
        <span class="nav-count">{stats.mit_highlights}</span>
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

  <!-- Sammlungen -->
  {#if sammlungenStore.sammlungen.length > 0}
    <div class="sidebar-divider"></div>
    <div class="section-label">Sammlungen</div>
    <div class="sammlungen-list">
      {#each sammlungenStore.sammlungen as s (s.id)}
        <button
          class="sammlung-btn"
          class:active={activeSammlung === String(s.id)}
          onclick={() => toggleSammlung(s.id)}
          title={s.name}
        >
          <span class="sammlung-dot" style="background-color: {s.color}"></span>
          <span class="sammlung-name">{s.name}</span>
          {#if s.buch_anzahl > 0}
            <span class="sammlung-count">{s.buch_anzahl}</span>
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
      href="/authors"
      class="nav-item"
      class:active={route.path === "/authors" || route.path.startsWith("/author/")}
    >
      <span class="nav-icon"><i class="fa-solid fa-users"></i></span>
      <span class="nav-label">Autoren</span>
      {#if stats.autoren > 0}
        <span class="nav-count">{stats.autoren}</span>
      {/if}
    </a>
    <a
      href="/import"
      class="nav-item"
      class:active={route.path === "/import"}
    >
      <span class="nav-icon"><i class="fa-solid fa-file-import"></i></span>
      <span class="nav-label">Import</span>
    </a>
    <button class="nav-item" class:active={ui.scratchPadOpen} onclick={() => ui.toggleScratchPad()}
      title="Schnelle Notizen ohne Buchzuordnung"
    >
      <span class="nav-icon"><i class="fa-solid fa-note-sticky" style="color: var(--color-warning)"></i></span>
      <span class="nav-label">Schnellnotiz</span>
      {#if schnellnotizWoerter > 0}
        <span class="nav-count">{schnellnotizWoerter} Wörter</span>
      {/if}
    </button>
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
  <div class="sidebar-version">
    BücherFreunde v{version}
    {#if updateVerfuegbar}
      <span class="update-hint" title="Version {remoteVersion} verfügbar - ./update.sh auf dem Server ausführen">
        <i class="fa-solid fa-arrow-up"></i> {remoteVersion}
      </span>
    {/if}
  </div>
</aside>

<style>
  .sidebar {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border-right: 1px solid var(--glass-border);
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
    background: var(--glass-border);
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
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
  }

  .nav-item.active {
    background: color-mix(in srgb, var(--color-accent) 50%, transparent);
    backdrop-filter: blur(var(--glass-blur-btn));
    border: 1px solid color-mix(in srgb, var(--color-accent) 30%, transparent);
    color: #fff;
  }

  .nav-item.active .nav-icon i {
    color: #fff !important;
  }

  .nav-item.active .nav-count {
    color: #fff;
    opacity: 0.8;
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
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
  }

  .cat-btn.active {
    background: color-mix(in srgb, var(--color-accent) 20%, transparent);
    backdrop-filter: blur(var(--glass-blur-btn));
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
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .cat-btn.active .cat-count {
    color: var(--color-accent);
  }

  /* Gelesen/Ungelesen Toggle */
  .gelesen-sep {
    opacity: 0.3;
    margin: 0 0.1rem;
    font-weight: 400;
  }

  .gelesen-label {
    transition: opacity 0.12s, font-weight 0.12s;
  }

  .gelesen-active {
    font-weight: 700;
  }

  .gelesen-dim {
    opacity: 0.35;
    font-weight: 400;
  }

  .gelesen-counts {
    display: inline-flex;
    align-items: center;
    gap: 0;
  }

  .empty-hint {
    padding: 0.5rem 0.75rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Sammlungen */
  .sammlungen-list {
    display: flex;
    flex-direction: column;
    gap: 1px;
    max-height: 200px;
    overflow-y: auto;
  }

  .sammlung-btn {
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

  .sammlung-btn:hover {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
  }

  .sammlung-btn.active {
    background: color-mix(in srgb, var(--color-accent) 20%, transparent);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-accent);
    font-weight: 600;
  }

  .sammlung-dot {
    width: 7px;
    height: 7px;
    border-radius: 3px;
    flex-shrink: 0;
  }

  .sammlung-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sammlung-count {
    font-size: 0.5625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .sammlung-btn.active .sammlung-count {
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

  .update-hint {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    margin-left: 0.25rem;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    background: color-mix(in srgb, var(--color-accent) 20%, transparent);
    color: var(--color-accent);
    font-weight: 600;
    cursor: help;
    opacity: 1;
  }
</style>
