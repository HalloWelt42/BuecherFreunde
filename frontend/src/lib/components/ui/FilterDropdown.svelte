<script>
  let {
    label = "Filter",
    icon = "fa-filter",
    items = [],
    selected = [],
    labelKey = "name",
    valueKey = "id",
    countKey = "buch_anzahl",
    searchPlaceholder = "Suchen...",
    onchange = () => {},
  } = $props();

  let open = $state(false);
  let search = $state("");
  let dropdownEl = $state(null);

  let filtered = $derived(
    search
      ? items.filter((item) =>
          String(item[labelKey]).toLowerCase().includes(search.toLowerCase()),
        )
      : items.slice(0, 50),
  );

  let selectedCount = $derived(selected.length);

  function toggle(value) {
    const strVal = String(value);
    const next = selected.includes(strVal)
      ? selected.filter((v) => v !== strVal)
      : [...selected, strVal];
    onchange(next);
  }

  function isSelected(value) {
    return selected.includes(String(value));
  }

  function clearSelection() {
    onchange([]);
  }

  function handleClickOutside(e) {
    if (dropdownEl && !dropdownEl.contains(e.target)) {
      open = false;
    }
  }

  $effect(() => {
    if (open) {
      document.addEventListener("click", handleClickOutside, true);
      return () => document.removeEventListener("click", handleClickOutside, true);
    }
  });

  $effect(() => {
    if (!open) search = "";
  });
</script>

<div class="filter-dropdown" bind:this={dropdownEl}>
  <button
    class="dropdown-trigger"
    class:has-selection={selectedCount > 0}
    onclick={() => (open = !open)}
  >
    <i class="fa-solid {icon}"></i>
    <span class="trigger-label">{label}</span>
    {#if selectedCount > 0}
      <span class="trigger-count">{selectedCount}</span>
    {/if}
    <i class="fa-solid fa-chevron-down trigger-arrow" class:rotated={open}></i>
  </button>

  {#if open}
    <div class="dropdown-panel">
      <div class="dropdown-search">
        <i class="fa-solid fa-magnifying-glass search-icon"></i>
        <input
          type="text"
          class="search-input"
          placeholder="{searchPlaceholder} ({items.length} gesamt)"
          bind:value={search}
        />
        {#if search}
          <button class="search-clear" onclick={() => (search = "")}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        {/if}
      </div>

      {#if selectedCount > 0}
        <button class="dropdown-clear" onclick={clearSelection}>
          <i class="fa-solid fa-xmark"></i> Auswahl aufheben ({selectedCount})
        </button>
      {/if}

      <div class="dropdown-list">
        {#each filtered as item (item[valueKey])}
          <button
            class="dropdown-item"
            class:selected={isSelected(item[valueKey])}
            onclick={() => toggle(item[valueKey])}
          >
            <span class="item-check">
              {#if isSelected(item[valueKey])}
                <i class="fa-solid fa-square-check"></i>
              {:else}
                <i class="fa-regular fa-square"></i>
              {/if}
            </span>
            <span class="item-label">{item[labelKey]}</span>
            {#if item[countKey] != null}
              <span class="item-count">{item[countKey]}</span>
            {/if}
          </button>
        {/each}
        {#if filtered.length === 0}
          <div class="dropdown-empty">
            <i class="fa-solid fa-magnifying-glass"></i>
            Keine Treffer
          </div>
        {/if}
        {#if !search && items.length > 50}
          <div class="dropdown-hint">
            <i class="fa-solid fa-info-circle"></i>
            {items.length - 50} weitere - Suche nutzen
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .filter-dropdown {
    position: relative;
  }

  .dropdown-trigger {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.3125rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s;
    white-space: nowrap;
  }

  .dropdown-trigger:hover {
    border-color: var(--color-accent);
    color: var(--color-text-primary);
  }

  .dropdown-trigger.has-selection {
    border-color: var(--color-accent);
    background-color: var(--color-accent-light);
    color: var(--color-accent);
  }

  .trigger-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.125rem;
    height: 1.125rem;
    padding: 0 0.25rem;
    border-radius: 999px;
    background-color: var(--color-accent);
    color: #fff;
    font-size: 0.625rem;
    font-weight: 700;
    font-family: var(--font-mono);
  }

  .trigger-arrow {
    font-size: 0.5rem;
    transition: transform 0.15s;
    margin-left: 0.125rem;
  }

  .trigger-arrow.rotated {
    transform: rotate(180deg);
  }

  .dropdown-panel {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    min-width: 260px;
    max-width: 320px;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    z-index: 100;
    overflow: hidden;
  }

  .dropdown-search {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.625rem;
    border-bottom: 1px solid var(--color-border);
  }

  .search-icon {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .search-input {
    flex: 1;
    border: none;
    background: none;
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: var(--font-sans);
    outline: none;
  }

  .search-input::placeholder {
    color: var(--color-text-muted);
  }

  .search-clear {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.625rem;
    cursor: pointer;
  }

  .search-clear:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .dropdown-clear {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    width: 100%;
    padding: 0.375rem 0.625rem;
    border: none;
    border-bottom: 1px solid var(--color-border);
    background: none;
    color: var(--color-error);
    font-size: 0.6875rem;
    cursor: pointer;
    text-align: left;
  }

  .dropdown-clear:hover {
    background-color: color-mix(in srgb, var(--color-error) 8%, transparent);
  }

  .dropdown-list {
    max-height: 280px;
    overflow-y: auto;
    padding: 0.25rem 0;
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.375rem 0.625rem;
    border: none;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
    text-align: left;
    transition: background-color 0.08s;
  }

  .dropdown-item:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .dropdown-item.selected {
    color: var(--color-text-primary);
    font-weight: 500;
  }

  .item-check {
    font-size: 0.875rem;
    width: 1rem;
    text-align: center;
    color: var(--color-text-muted);
  }

  .dropdown-item.selected .item-check {
    color: var(--color-accent);
  }

  .item-label {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-count {
    font-size: 0.625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    padding: 0.0625rem 0.375rem;
    border-radius: 999px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  .dropdown-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.375rem;
    padding: 1rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .dropdown-hint {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.625rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    border-top: 1px solid var(--color-border);
  }
</style>
