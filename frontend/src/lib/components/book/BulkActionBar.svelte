<script>
  import { selectionStore } from "../../stores/selection.svelte.js";
  import { bulkAction } from "../../api/books.js";
  import { booksStore } from "../../stores/books.svelte.js";
  import { categoriesStore } from "../../stores/categories.svelte.js";
  import { ui } from "../../stores/ui.svelte.js";

  let confirmDelete = $state(false);
  let processing = $state(false);
  let showCatDropdown = $state(false);
  let catSearch = $state("");
  let catSearchInput = $state(null);

  let filteredKategorien = $derived.by(() => {
    const all = categoriesStore.kategorien;
    if (!catSearch.trim()) return all;
    const q = catSearch.trim().toLowerCase();
    return all.filter(k => k.name.toLowerCase().includes(q));
  });

  // Titel der ausgewählten Bücher
  let selectedTitles = $derived.by(() => {
    if (selectionStore.count === 0) return [];
    return booksStore.books
      .filter(b => selectionStore.has(b.id))
      .map(b => b.title)
      .slice(0, 5);
  });

  function handleKeydown(e) {
    if (!selectionStore.active) return;
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      confirmDelete = true;
    }
    if (e.key === "Escape") {
      if (confirmDelete) {
        confirmDelete = false;
      } else {
        selectionStore.clear();
      }
    }
  }

  async function handleAction(aktion, wert) {
    processing = true;
    try {
      await bulkAction(selectionStore.ids, aktion, wert);
      selectionStore.clear();
      booksStore.laden_();
    } catch (e) {
      console.error("Bulk-Aktion fehlgeschlagen:", e);
    } finally {
      processing = false;
      confirmDelete = false;
      showCatDropdown = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if selectionStore.editMode || selectionStore.active}
  <div class="bulk-bar" style="left: calc({ui.sidebarOpen ? 'var(--sidebar-width, 280px)' : '0px'} + (100vw - {ui.sidebarOpen ? 'var(--sidebar-width, 280px)' : '0px'}) / 2)">
    <div class="bulk-info">
      <i class="fa-solid fa-check-double"></i>
      <strong>{selectionStore.count}</strong> ausgewählt
      {#if selectedTitles.length > 0}
        <span class="bulk-titles" title={selectedTitles.join(", ")}>
          -- {selectedTitles.join(", ")}{selectionStore.count > 5 ? ` (+${selectionStore.count - 5})` : ""}
        </span>
      {/if}
    </div>

    <div class="bulk-actions">
      <button
        class="bulk-btn"
        onclick={() => handleAction("favorit", true)}
        disabled={processing}
        title="Zu Favoriten"
      >
        <i class="fa-solid fa-heart"></i> Favorit
      </button>

      <button
        class="bulk-btn"
        onclick={() => handleAction("zu_lesen", true)}
        disabled={processing}
        title="Zur Leseliste"
      >
        <i class="fa-solid fa-bookmark"></i> Leseliste
      </button>

      <div class="bulk-dropdown-wrap">
        <button
          class="bulk-btn"
          onclick={() => { showCatDropdown = !showCatDropdown; catSearch = ""; if (showCatDropdown) setTimeout(() => catSearchInput?.focus(), 50); }}
          disabled={processing}
        >
          <i class="fa-solid fa-folder-plus"></i> Kategorie
          <i class="fa-solid fa-chevron-up" style="font-size: 0.5rem"></i>
        </button>
        {#if showCatDropdown}
          <div class="bulk-dropdown">
            <div class="dropdown-search">
              <i class="fa-solid fa-magnifying-glass dropdown-search-icon"></i>
              <input
                type="text"
                class="dropdown-search-input"
                placeholder="Kategorie suchen..."
                bind:value={catSearch}
                bind:this={catSearchInput}
                onkeydown={(e) => { if (e.key === "Escape") { showCatDropdown = false; } }}
              />
            </div>
            <div class="dropdown-list">
              {#if filteredKategorien.length === 0}
                <div class="dropdown-empty">{catSearch ? "Keine Treffer" : "Keine Kategorien"}</div>
              {:else}
                {#each filteredKategorien as kat (kat.id)}
                  <button
                    class="dropdown-option"
                    onclick={() => handleAction("kategorie_zuweisen", kat.id)}
                  >
                    {#if kat.icon}<i class="fa-solid {kat.icon}"></i>{/if}
                    {kat.name}
                    {#if kat.buch_anzahl}<span class="dropdown-count">{kat.buch_anzahl}</span>{/if}
                  </button>
                {/each}
              {/if}
            </div>
          </div>
        {/if}
      </div>

      {#if confirmDelete}
        <div class="delete-confirm">
          <span>Wirklich löschen?</span>
          <button
            class="bulk-btn danger"
            onclick={() => handleAction("loeschen")}
            disabled={processing}
          >
            {#if processing}
              <i class="fa-solid fa-spinner fa-spin"></i>
            {:else}
              <i class="fa-solid fa-check"></i> Ja, löschen
            {/if}
          </button>
          <button
            class="bulk-btn"
            onclick={() => (confirmDelete = false)}
          >
            Abbrechen
          </button>
        </div>
      {:else}
        <button
          class="bulk-btn danger"
          onclick={() => (confirmDelete = true)}
          disabled={processing}
        >
          <i class="fa-solid fa-trash"></i> Löschen
        </button>
      {/if}
    </div>

    <button
      class="bulk-close"
      onclick={() => selectionStore.clear()}
      title="Auswahl aufheben"
    >
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>
{/if}

<style>
  .bulk-bar {
    position: fixed;
    bottom: 2rem;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.625rem 1.25rem;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-accent);
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    z-index: 200;
    backdrop-filter: blur(12px);
  }

  .bulk-info {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--color-accent);
    white-space: nowrap;
    max-width: 40vw;
    overflow: hidden;
  }

  .bulk-titles {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .bulk-actions {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .bulk-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.1s;
  }

  .bulk-btn:hover:not(:disabled) {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
    border-color: var(--color-accent);
  }

  .bulk-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .bulk-btn.danger {
    color: var(--color-error);
    border-color: color-mix(in srgb, var(--color-error) 30%, transparent);
  }

  .bulk-btn.danger:hover:not(:disabled) {
    background-color: color-mix(in srgb, var(--color-error) 12%, transparent);
    border-color: var(--color-error);
  }

  .delete-confirm {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    color: var(--color-error);
  }

  .bulk-dropdown-wrap {
    position: relative;
  }

  .bulk-dropdown {
    position: absolute;
    bottom: calc(100% + 4px);
    left: 0;
    min-width: 240px;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dropdown-search {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem;
    border-bottom: 1px solid var(--color-border);
  }

  .dropdown-search-icon {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .dropdown-search-input {
    flex: 1;
    border: none;
    background: none;
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: var(--font-sans);
    outline: none;
  }

  .dropdown-search-input::placeholder {
    color: var(--color-text-muted);
  }

  .dropdown-list {
    max-height: 240px;
    overflow-y: auto;
    padding: 0.25rem 0;
  }

  .dropdown-option {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    width: 100%;
    padding: 0.375rem 0.75rem;
    border: none;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    text-align: left;
    cursor: pointer;
  }

  .dropdown-option:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .dropdown-option i {
    font-size: 0.6875rem;
    width: 1rem;
    text-align: center;
    color: var(--color-text-muted);
  }

  .dropdown-count {
    margin-left: auto;
    font-size: 0.625rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }

  .dropdown-empty {
    padding: 0.75rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    text-align: center;
  }

  .bulk-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
  }

  .bulk-close:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }
</style>
