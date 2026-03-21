<script>
  import { navigate } from "../../router.svelte.js";
  import { vorschlaege } from "../../api/search.js";

  let query = $state("");
  let suggestions = $state([]);
  let showDropdown = $state(false);
  let selectedIndex = $state(-1);
  let debounceTimer;

  function onInput() {
    clearTimeout(debounceTimer);
    if (query.trim().length < 2) {
      suggestions = [];
      showDropdown = false;
      return;
    }
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

  function onKeydown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        const s = suggestions[selectedIndex];
        showDropdown = false;
        navigate(`/book/${s.id}`);
        return;
      }
      if (query.trim()) {
        showDropdown = false;
        navigate(`/search?q=${encodeURIComponent(query.trim())}`);
      }
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, -1);
    } else if (event.key === "Escape") {
      showDropdown = false;
    }
  }

  function selectSuggestion(s) {
    showDropdown = false;
    navigate(`/book/${s.id}`);
  }

  function onBlur() {
    // Verzögert schließen damit Klick auf Vorschlag noch funktioniert
    setTimeout(() => {
      showDropdown = false;
    }, 200);
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
    onfocus={() => {
      if (suggestions.length > 0) showDropdown = true;
    }}
  />

  {#if showDropdown}
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
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-primary);
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
    background-color: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    list-style: none;
    padding: 0.25rem;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  .suggestion-item {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    border: none;
    background: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
    color: var(--color-text-primary);
  }

  .suggestion-item:hover,
  .suggestion-item.selected {
    background-color: var(--color-bg-tertiary);
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
