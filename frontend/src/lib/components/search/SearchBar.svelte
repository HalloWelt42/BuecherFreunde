<script>
  import { navigate } from "../../router.svelte.js";
  import { vorschlaege } from "../../api/search.js";

  const MAX_HISTORY = 50;
  const STORAGE_KEY = "search_history";

  let query = $state("");
  let suggestions = $state([]);
  let showDropdown = $state(false);
  let selectedIndex = $state(-1);
  let debounceTimer;
  let showHistory = $state(false);

  // Suchhistorie aus localStorage laden
  let history = $state(ladeHistorie());

  function ladeHistorie() {
    try {
      const h = localStorage.getItem(STORAGE_KEY);
      return h ? JSON.parse(h) : [];
    } catch { return []; }
  }

  function speichereHistorie() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch { /* QuotaExceeded */ }
  }

  function addToHistory(term) {
    const clean = term.trim();
    if (!clean || clean.length < 2) return;
    // Duplikat entfernen, vorne einfügen
    history = [clean, ...history.filter(h => h !== clean)].slice(0, MAX_HISTORY);
    speichereHistorie();
  }

  function entferneAusHistorie(term, event) {
    event.stopPropagation();
    event.preventDefault();
    history = history.filter(h => h !== term);
    speichereHistorie();
  }

  function loescheHistorie() {
    history = [];
    speichereHistorie();
    showHistory = false;
  }

  function onInput() {
    clearTimeout(debounceTimer);
    if (query.trim().length < 2) {
      suggestions = [];
      // Bei leerem Input: Historie anzeigen
      showHistory = query.trim().length === 0 && history.length > 0;
      showDropdown = showHistory;
      return;
    }
    showHistory = false;
    debounceTimer = setTimeout(async () => {
      try {
        const result = await vorschlaege(query.trim());
        suggestions = result.vorschlaege || result.suggestions || [];
        showDropdown = suggestions.length > 0;
        selectedIndex = -1;
      } catch {
        suggestions = [];
        showDropdown = false;
      }
    }, 300);
  }

  function doSearch(term) {
    const t = term.trim();
    if (!t) return;
    addToHistory(t);
    showDropdown = false;
    showHistory = false;
    navigate(`/search?q=${encodeURIComponent(t)}`);
  }

  function onKeydown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      if (showHistory && selectedIndex >= 0 && selectedIndex < history.length) {
        query = history[selectedIndex];
        doSearch(query);
        return;
      }
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        const s = suggestions[selectedIndex];
        addToHistory(query.trim());
        showDropdown = false;
        navigate(`/book/${s.id}`);
        return;
      }
      if (query.trim()) {
        doSearch(query);
      }
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      const max = showHistory ? history.length - 1 : suggestions.length - 1;
      selectedIndex = Math.min(selectedIndex + 1, max);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, -1);
    } else if (event.key === "Escape") {
      showDropdown = false;
      showHistory = false;
    }
  }

  function selectSuggestion(s) {
    addToHistory(query.trim());
    showDropdown = false;
    navigate(`/book/${s.id}`);
  }

  function selectHistoryItem(term) {
    query = term;
    showHistory = false;
    doSearch(term);
  }

  function onBlur() {
    setTimeout(() => {
      showDropdown = false;
      showHistory = false;
    }, 200);
  }

  function onFocus() {
    if (query.trim().length >= 2 && suggestions.length > 0) {
      showDropdown = true;
    } else if (query.trim().length === 0 && history.length > 0) {
      showHistory = true;
      showDropdown = true;
    }
  }
</script>

<div class="search-bar">
  <input
    type="search"
    placeholder="Bücher durchsuchen..."
    class="search-input"
    bind:value={query}
    oninput={onInput}
    onkeydown={onKeydown}
    onblur={onBlur}
    onfocus={onFocus}
  />

  {#if showDropdown && showHistory && history.length > 0}
    <!-- Suchhistorie -->
    <div class="suggestions history-dropdown">
      <div class="history-header">
        <span class="history-label"><i class="fa-solid fa-clock-rotate-left"></i> Suchverlauf</span>
        <button class="history-clear" onmousedown={(e) => { e.preventDefault(); loescheHistorie(); }}>
          Verlauf löschen
        </button>
      </div>
      <ul>
        {#each history as term, i (term)}
          <li>
            <div
              class="suggestion-item history-item"
              class:selected={i === selectedIndex}
              role="option"
              aria-selected={i === selectedIndex}
              onmousedown={() => selectHistoryItem(term)}
            >
              <i class="fa-solid fa-clock-rotate-left history-icon"></i>
              <span class="history-term">{term}</span>
              <span
                class="history-remove"
                role="button"
                tabindex="-1"
                onmousedown={(e) => entferneAusHistorie(term, e)}
                title="Aus Verlauf entfernen"
              >
                <i class="fa-solid fa-xmark"></i>
              </span>
            </div>
          </li>
        {/each}
      </ul>
    </div>
  {:else if showDropdown && suggestions.length > 0}
    <!-- Autocomplete-Vorschläge -->
    <ul class="suggestions">
      {#each suggestions as suggestion, i (suggestion.id)}
        <li>
          <button
            class="suggestion-item"
            class:selected={i === selectedIndex}
            onmousedown={() => selectSuggestion(suggestion)}
          >
            <span class="suggestion-title">{@html suggestion.titel}</span>
            {#if suggestion.autor}
              <span class="suggestion-author">{@html suggestion.autor}</span>
            {/if}
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .search-bar {
    position: relative;
    flex: 1;
    max-width: 600px;
  }

  .search-input {
    width: 100%;
    padding: 0.5rem 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--glass-placeholder);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
    font-family: var(--font-sans);
    font-size: 0.875rem;
  }

  .search-input:focus {
    outline: 2px solid var(--color-accent);
    outline-offset: -1px;
  }

  .suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    margin-top: 4px;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    list-style: none;
    padding: 0.25rem;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    max-height: 400px;
    overflow-y: auto;
  }

  .history-dropdown {
    padding: 0;
  }

  .history-dropdown ul {
    list-style: none;
    padding: 0.25rem;
    margin: 0;
  }

  .history-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0.75rem 0.25rem;
    border-bottom: 1px solid var(--glass-border);
    margin-bottom: 0.25rem;
  }

  .history-label {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .history-clear {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
  }

  .history-clear:hover {
    color: var(--color-error);
    background: color-mix(in srgb, var(--color-error) 10%, transparent);
  }

  .suggestion-item {
    display: flex;
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    border: none;
    background: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    color: var(--color-text-primary);
    align-items: center;
    gap: 0.5rem;
  }

  .suggestion-item:hover,
  .suggestion-item.selected {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
  }

  .history-item {
    padding: 0.375rem 0.75rem;
  }

  .history-icon {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .history-term {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .history-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    background: none;
    color: var(--color-text-muted);
    cursor: pointer;
    border-radius: 3px;
    font-size: 0.625rem;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.1s;
  }

  .suggestion-item:hover .history-remove {
    opacity: 1;
  }

  .history-remove:hover {
    color: var(--color-error);
    background: color-mix(in srgb, var(--color-error) 10%, transparent);
  }

  .suggestion-title {
    font-weight: 500;
  }

  .suggestion-author {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin-left: 0.5rem;
  }
</style>
