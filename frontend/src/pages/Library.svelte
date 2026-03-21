<script>
  import { ui } from "../lib/stores/ui.svelte.js";
  import { booksStore } from "../lib/stores/books.svelte.js";
  import { categoriesStore } from "../lib/stores/categories.svelte.js";
  import { sammlungenStore } from "../lib/stores/tags.svelte.js";
  import BookGrid from "../lib/components/book/BookGrid.svelte";
  import BookList from "../lib/components/book/BookList.svelte";
  import FilterDropdown from "../lib/components/ui/FilterDropdown.svelte";
  import BulkActionBar from "../lib/components/book/BulkActionBar.svelte";
  import { selectionStore } from "../lib/stores/selection.svelte.js";

  import { route, navigate } from "../lib/router.svelte.js";
  import { onMount, onDestroy, untrack, tick } from "svelte";
  import { onBooksChanged } from "../lib/stores/processes.svelte.js";

  let loadTrigger = $state(null);
  let scrollContainer = $state(null);
  let observer = null;

  const sortOptions = [
    { value: "titel", label: "Titel", icon: "fa-font" },
    { value: "autor", label: "Autor", icon: "fa-user" },
    { value: "datum", label: "Hinzugefügt", icon: "fa-calendar" },
    { value: "groesse", label: "Dateigröße", icon: "fa-weight-hanging" },
  ];

  const formatItems = [
    { id: "pdf", name: "PDF", buch_anzahl: null },
    { id: "epub", name: "EPUB", buch_anzahl: null },
    { id: "mobi", name: "MOBI", buch_anzahl: null },
    { id: "txt", name: "TXT", buch_anzahl: null },
    { id: "md", name: "Markdown", buch_anzahl: null },
  ];

  const ratingItems = [
    { id: "5", name: "5 Sterne", buch_anzahl: null },
    { id: "4", name: "4+ Sterne", buch_anzahl: null },
    { id: "3", name: "3+ Sterne", buch_anzahl: null },
    { id: "2", name: "2+ Sterne", buch_anzahl: null },
    { id: "1", name: "1+ Stern", buch_anzahl: null },
  ];

  let sortBy = $state("titel");
  let sortDir = $state("asc");

  // Ausgewählte Filter aus URL lesen
  let selectedCategories = $derived.by(() => {
    const v = new URLSearchParams(route.qs || "").get("category");
    return v ? v.split(",") : [];
  });
  let selectedSammlungen = $derived.by(() => {
    const v = new URLSearchParams(route.qs || "").get("sammlung");
    return v ? [v] : [];
  });
  let selectedFormats = $derived.by(() => {
    const v = new URLSearchParams(route.qs || "").get("file_format");
    return v ? v.split(",") : [];
  });
  let selectedRating = $derived.by(() => {
    const v = new URLSearchParams(route.qs || "").get("min_rating");
    return v ? [v] : [];
  });
  let isFavorite = $derived(new URLSearchParams(route.qs || "").get("is_favorite") === "true");
  let isToRead = $derived(new URLSearchParams(route.qs || "").get("is_to_read") === "true");

  let hasActiveFilters = $derived(
    selectedCategories.length > 0 ||
    selectedSammlungen.length > 0 ||
    selectedFormats.length > 0 ||
    selectedRating.length > 0 ||
    isFavorite || isToRead
  );

  function updateUrlParam(key, values) {
    const params = new URLSearchParams(route.qs || "");
    if (values.length > 0) {
      params.set(key, values.join(","));
    } else {
      params.delete(key);
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  function toggleBoolFilter(key) {
    const params = new URLSearchParams(route.qs || "");
    if (params.get(key)) {
      params.delete(key);
    } else {
      params.set(key, "true");
    }
    const qs = params.toString();
    navigate(qs ? `/?${qs}` : "/");
  }

  function clearAllFilters() {
    navigate("/");
  }

  // URL-Parameter als Filter übernehmen - immer vollständig setzen
  $effect(() => {
    const params = new URLSearchParams(route.qs || "");
    const newFilter = {
      kategorie: params.get("category") || null,
      // tag entfernt - ersetzt durch sammlung
      sammlung: params.get("sammlung") ? Number(params.get("sammlung")) : null,
      favorit: params.get("is_favorite") === "true" ? true : null,
      zu_lesen: params.get("is_to_read") === "true" ? true : null,
      bewertung_min: params.get("min_rating") ? Number(params.get("min_rating")) : null,
      format: params.get("file_format") || null,
      gelesen: params.has("gelesen") ? params.get("gelesen") === "true" : null,
      hat_isbn: params.has("hat_isbn") ? params.get("hat_isbn") === "true" : null,
      weiterlesen: params.get("weiterlesen") === "true" ? true : null,
      sortierung: sortBy,
      richtung: sortDir,
      pro_seite: 48,
    };
    untrack(() => booksStore.setFilter(newFilter));
  });

  function mehrLaden() {
    booksStore.mehrLaden();
  }

  function onSortChange(value) {
    sortBy = value;
    booksStore.setFilter({ ...booksStore.filter, sortierung: value, richtung: sortDir });
  }

  function toggleSortDir() {
    sortDir = sortDir === "asc" ? "desc" : "asc";
    booksStore.setFilter({ ...booksStore.filter, richtung: sortDir });
  }

  function setViewMode(mode) {
    ui.viewMode = mode;
  }

  let _unsubProcesses;

  onMount(() => {
    categoriesStore.aktualisieren();
    sammlungenStore.aktualisieren();

    // Bei neuen Import-Ergebnissen Bibliothek automatisch aktualisieren
    _unsubProcesses = onBooksChanged(() => {
      booksStore.laden_();
      categoriesStore.aktualisieren();
    });
  });

  // Scroll-Container finden (grid-main ist der übergeordnete Scroll-Container)
  onMount(() => {
    scrollContainer = document.querySelector(".grid-main");
  });

  // Infinite Scroll: Intersection Observer auf das Load-Trigger-Element
  $effect(() => {
    if (!loadTrigger || !scrollContainer) return;
    if (observer) observer.disconnect();

    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !booksStore.laden) {
          booksStore.mehrLaden();
        }
      },
      { root: scrollContainer, rootMargin: "400px" },
    );
    observer.observe(loadTrigger);

    return () => observer?.disconnect();
  });

  onDestroy(() => {
    if (_unsubProcesses) _unsubProcesses();
    if (observer) observer.disconnect();
  });
</script>

<div class="library-page">
  <!-- Toolbar -->
  <div class="toolbar">
    <div class="toolbar-row">
      <span class="result-count">
        <i class="fa-solid fa-book"></i>
        <strong>{booksStore.total}</strong> Bücher
      </span>

      {#if selectionStore.active}
        <button
          class="select-all-btn"
          onclick={() => selectionStore.selectAll(booksStore.books.map(b => b.id))}
        >
          <i class="fa-solid fa-check-double"></i> Alle
        </button>
      {/if}

      <!-- Filter-Dropdowns -->
      <div class="filter-group">
        <FilterDropdown
          label="Kategorien"
          icon="fa-folder"
          items={categoriesStore.kategorien}
          selected={selectedCategories}
          searchPlaceholder="Kategorie suchen..."
          onchange={(vals) => updateUrlParam("category", vals)}
        />
        <FilterDropdown
          label="Sammlungen"
          icon="fa-layer-group"
          items={sammlungenStore.sammlungen}
          selected={selectedSammlungen}
          searchPlaceholder="Sammlung suchen..."
          onchange={(vals) => updateUrlParam("sammlung", vals)}
        />
        <FilterDropdown
          label="Format"
          icon="fa-file"
          items={formatItems}
          selected={selectedFormats}
          searchPlaceholder="Format suchen..."
          onchange={(vals) => updateUrlParam("file_format", vals)}
        />
        <FilterDropdown
          label="Bewertung"
          icon="fa-star"
          items={ratingItems}
          selected={selectedRating}
          searchPlaceholder="Bewertung..."
          onchange={(vals) => updateUrlParam("min_rating", vals)}
        />

        <button
          class="toggle-btn"
          class:active={isFavorite}
          onclick={() => toggleBoolFilter("is_favorite")}
          title="Nur Favoriten"
        >
          <i class="fa-solid fa-heart"></i>
        </button>
        <button
          class="toggle-btn"
          class:active={isToRead}
          onclick={() => toggleBoolFilter("is_to_read")}
          title="Leseliste"
        >
          <i class="fa-solid fa-bookmark"></i>
        </button>

        {#if hasActiveFilters}
          <button class="clear-filters-btn" onclick={clearAllFilters} title="Alle Filter entfernen">
            <i class="fa-solid fa-filter-circle-xmark"></i>
          </button>
        {/if}
      </div>

      <!-- Sortierung + Ansicht -->
      <div class="toolbar-controls">
        <div class="sort-group">
          <select
            class="sort-select"
            value={sortBy}
            onchange={(e) => onSortChange(e.target.value)}
          >
            {#each sortOptions as opt (opt.value)}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
          <button
            class="sort-dir-btn"
            onclick={toggleSortDir}
            title={sortDir === "asc" ? "Aufsteigend" : "Absteigend"}
          >
            <i class="fa-solid {sortDir === 'asc' ? 'fa-arrow-up-a-z' : 'fa-arrow-down-z-a'}"></i>
          </button>
        </div>

        <div class="view-group">
          <button
            class="view-btn"
            class:active={ui.viewMode === "list"}
            onclick={() => setViewMode("list")}
            title="Kompakte Liste"
          >
            <i class="fa-solid fa-list"></i>
          </button>
          <button
            class="view-btn"
            class:active={ui.viewMode === "detail-list"}
            onclick={() => setViewMode("detail-list")}
            title="Detailliste"
          >
            <i class="fa-solid fa-table-list"></i>
          </button>
          <button
            class="view-btn"
            class:active={ui.viewMode === "grid"}
            onclick={() => setViewMode("grid")}
            title="Kacheln"
          >
            <i class="fa-solid fa-table-cells"></i>
          </button>
          <button
            class="view-btn"
            class:active={ui.viewMode === "grid-large"}
            onclick={() => setViewMode("grid-large")}
            title="Große Kacheln"
          >
            <i class="fa-solid fa-table-cells-large"></i>
          </button>
          <button
            class="view-btn"
            class:active={ui.viewMode === "covers"}
            onclick={() => setViewMode("covers")}
            title="Nur Cover"
          >
            <i class="fa-solid fa-image"></i>
          </button>

          <button
            class="view-btn edit-mode-btn"
            class:active={selectionStore.editMode}
            onclick={() => selectionStore.toggleEditMode()}
            title="Bearbeitungsmodus"
          >
            <i class="fa-solid fa-pen-to-square"></i>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Content -->
  <div class="library-content">
    {#if booksStore.laden && booksStore.books.length === 0}
      <div class="state-message">
        <i class="fa-solid fa-spinner fa-spin state-icon"></i>
        <p>Bücher werden geladen...</p>
      </div>
    {:else if booksStore.fehler}
      <div class="state-message error">
        <i class="fa-solid fa-triangle-exclamation state-icon"></i>
        <p>Fehler: {booksStore.fehler}</p>
        <button class="retry-btn" onclick={() => booksStore.laden_()}>
          <i class="fa-solid fa-rotate-right"></i> Erneut versuchen
        </button>
      </div>
    {:else if booksStore.books.length === 0}
      <div class="state-message">
        <i class="fa-solid fa-book-open state-icon large"></i>
        <h2 class="state-title">Willkommen bei BücherFreunde</h2>
        <p class="state-text">Importiere dein erstes Buch, um loszulegen.</p>
        <a href="/import" class="btn-primary">
          <i class="fa-solid fa-file-import"></i> Bücher importieren
        </a>
      </div>
    {:else}
      {#if ui.viewMode === "covers"}
        <BookGrid books={booksStore.books} coversOnly={true} />
      {:else if ui.viewMode === "grid" || ui.viewMode === "grid-large"}
        <BookGrid books={booksStore.books} large={ui.viewMode === "grid-large"} />
      {:else if ui.viewMode === "detail-list"}
        <BookList
          books={booksStore.books}
          detailed={true}
          onSort={(col, dir) => {
            const map = { title: "titel", author: "autor", file_size: "groesse", rating: "bewertung", year: "jahr" };
            booksStore.setFilter({ ...booksStore.filter, sortierung: map[col] || col, richtung: dir });
          }}
        />
      {:else}
        <BookList
          books={booksStore.books}
          onSort={(col, dir) => {
            const map = { title: "titel", author: "autor", file_size: "groesse", rating: "bewertung", year: "jahr" };
            booksStore.setFilter({ ...booksStore.filter, sortierung: map[col] || col, richtung: dir });
          }}
        />
      {/if}

      {#if booksStore.books.length < booksStore.total}
        <div class="load-more" bind:this={loadTrigger}>
          {#if booksStore.laden}
            <div class="load-more-indicator">
              <i class="fa-solid fa-spinner fa-spin"></i> Wird geladen...
            </div>
          {:else}
            <div class="load-more-indicator">
              <span class="load-more-info">
                {booksStore.books.length} von {booksStore.total} Büchern
              </span>
            </div>
          {/if}
        </div>
      {/if}
    {/if}
  </div>
</div>

<BulkActionBar />

<style>
  .library-page {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  /* Toolbar */
  .toolbar {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
    position: sticky;
    top: -1.5rem;
    z-index: 5;
    background-color: var(--color-bg-primary);
    margin: -1.5rem -1.5rem 0;
    padding: 1.5rem 1.5rem 0.5rem;
  }

  .toolbar-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .result-count {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    display: flex;
    align-items: center;
    gap: 0.375rem;
    white-space: nowrap;
  }

  .result-count strong {
    color: var(--color-text-primary);
    font-weight: 600;
  }

  .result-count i {
    font-size: 0.75rem;
  }

  .select-all-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-accent);
    border-radius: 6px;
    background-color: var(--color-accent-light);
    color: var(--color-accent);
    font-size: 0.6875rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }

  .select-all-btn:hover {
    background-color: var(--color-accent);
    color: #fff;
  }

  /* Filter-Gruppe */
  .filter-group {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    flex: 1;
    flex-wrap: wrap;
  }

  .toggle-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.12s;
  }

  .toggle-btn:hover {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    border-color: var(--color-accent);
    color: var(--color-text-primary);
  }

  .toggle-btn.active {
    border-color: var(--color-accent);
    background-color: var(--color-accent-light);
    color: var(--color-accent);
  }

  .clear-filters-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid color-mix(in srgb, var(--color-error) 30%, transparent);
    border-radius: 6px;
    background: none;
    color: var(--color-error);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.12s;
  }

  .clear-filters-btn:hover {
    background-color: color-mix(in srgb, var(--color-error) 10%, transparent);
  }

  /* Sortierung + Ansicht */
  .toolbar-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-left: auto;
  }

  .sort-group {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .sort-select {
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--glass-placeholder);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: var(--font-sans);
    cursor: pointer;
  }

  .sort-dir-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.12s;
  }

  .sort-dir-btn:hover {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
  }

  /* Ansicht-Toggle */
  .view-group {
    display: flex;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    overflow: hidden;
  }

  .view-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.12s;
  }

  .view-btn:hover {
    color: var(--color-text-primary);
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
  }

  .view-btn.active {
    color: var(--color-accent);
    background-color: var(--color-accent-light);
  }

  .view-btn + .view-btn {
    border-left: 1px solid var(--color-border);
  }

  .edit-mode-btn {
    margin-left: 0.5rem;
    border-left: none !important;
    border-radius: 4px;
  }

  /* Content */
  .library-content {
    flex: 1;
  }

  /* Zustände */
  .state-message {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    gap: 0.75rem;
    text-align: center;
    color: var(--color-text-secondary);
  }

  .state-message.error {
    color: var(--color-error);
  }

  .state-icon {
    font-size: 2rem;
    opacity: 0.4;
  }

  .state-icon.large {
    font-size: 3.5rem;
    opacity: 0.25;
  }

  .state-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .state-text {
    font-size: 0.875rem;
    color: var(--color-text-muted);
    max-width: 300px;
  }

  .retry-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    cursor: pointer;
  }

  .retry-btn:hover {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    padding: 0.625rem 1.5rem;
    background-color: var(--color-accent);
    color: #fff;
    border-radius: 8px;
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
    transition: opacity 0.12s;
  }

  .btn-primary:hover {
    opacity: 0.9;
    color: #fff;
  }

  /* Mehr laden */
  .load-more {
    display: flex;
    justify-content: center;
    padding: 1.5rem 0;
  }

  .load-more-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .load-more-info {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
</style>
