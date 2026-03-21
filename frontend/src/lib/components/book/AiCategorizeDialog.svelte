<script>
  import Modal from "../ui/Modal.svelte";
  import { kategorisiere, uebernehmVorschlaege } from "../../api/ai.js";

  let { bookId = null, open = false, onClose = () => {}, onDone = () => {} } = $props();

  let status = $state("idle"); // idle, analyzing, done, error
  let suggestions = $state([]);
  let selected = $state({});
  let errorMsg = $state("");

  async function analysieren() {
    status = "analyzing";
    errorMsg = "";
    suggestions = [];
    selected = {};

    try {
      const result = await kategorisiere(bookId);
      suggestions = result.vorschlaege || result.suggestions || [];
      for (const s of suggestions) {
        const name = s.kategorie || s.category;
        selected[name] = true;
      }
      status = "done";
    } catch (e) {
      errorMsg = e.message || "KI-Dienst nicht erreichbar";
      status = "error";
    }
  }

  function toggleSelection(category) {
    selected[category] = !selected[category];
  }

  async function uebernehmen() {
    const akzeptiert = suggestions
      .filter((s) => selected[s.kategorie || s.category])
      .map((s) => s.kategorie || s.category);

    if (akzeptiert.length === 0) {
      onClose();
      return;
    }

    try {
      await uebernehmVorschlaege(bookId, akzeptiert);
      onDone();
      onClose();
    } catch (e) {
      errorMsg = e.message;
    }
  }

  function confidenceColor(confidence) {
    if (confidence >= 0.8) return "var(--color-success)";
    if (confidence >= 0.5) return "var(--color-warning)";
    return "var(--color-error)";
  }

  // Reset bei Öffnen
  $effect(() => {
    if (open) {
      status = "idle";
      suggestions = [];
      selected = {};
      errorMsg = "";
    }
  });
</script>

<Modal {open} title="KI-Kategorisierung" {onClose}>
  <div class="dialog-content">
    {#if status === "idle"}
      <p class="info-text">
        Die KI analysiert Titel, Autor und einen Textauszug des Buches und
        schlägt passende Kategorien vor.
      </p>
      <button class="btn btn-primary" onclick={analysieren}>
        Analysieren
      </button>

    {:else if status === "analyzing"}
      <div class="loading">
        <div class="spinner"></div>
        <p>KI analysiert das Buch...</p>
      </div>

    {:else if status === "error"}
      <div class="error">
        <p class="error-text">{errorMsg}</p>
        <button class="btn btn-secondary" onclick={analysieren}>
          Erneut versuchen
        </button>
      </div>

    {:else if status === "done"}
      {#if suggestions.length === 0}
        <p class="info-text">Keine Kategorievorschläge gefunden.</p>
      {:else}
        <div class="suggestions">
          {#each suggestions as suggestion (suggestion.kategorie || suggestion.category)}
            {@const name = suggestion.kategorie || suggestion.category}
            {@const conf = suggestion.konfidenz ?? suggestion.confidence ?? 0.5}
            <label class="suggestion-item">
              <input
                type="checkbox"
                checked={selected[name]}
                onchange={() => toggleSelection(name)}
              />
              <span class="suggestion-name">{name}</span>
              <div class="confidence-bar">
                <div
                  class="confidence-fill"
                  style="width: {conf * 100}%; background-color: {confidenceColor(conf)}"
                ></div>
              </div>
              <span class="confidence-value">
                {Math.round(conf * 100)}%
              </span>
            </label>
          {/each}
        </div>

        <div class="dialog-actions">
          <button class="btn btn-secondary" onclick={onClose}>
            Abbrechen
          </button>
          <button class="btn btn-primary" onclick={uebernehmen}>
            Übernehmen
          </button>
        </div>
      {/if}
    {/if}
  </div>
</Modal>

<style>
  .dialog-content {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .info-text {
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    line-height: 1.5;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    border: none;
  }

  .btn-primary {
    background-color: var(--color-accent);
    color: #fff;
  }

  .btn-secondary {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
  }

  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    padding: 2rem 0;
    color: var(--color-text-secondary);
  }

  .spinner {
    width: 2rem;
    height: 2rem;
    border: 3px solid var(--color-border);
    border-top-color: var(--color-accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .error {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .error-text {
    color: var(--color-error);
    font-size: 0.875rem;
  }

  .suggestions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .suggestion-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .suggestion-item:hover {
    background-color: var(--color-bg-tertiary);
  }

  .suggestion-item input[type="checkbox"] {
    accent-color: var(--color-accent);
  }

  .suggestion-name {
    flex: 1;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .confidence-bar {
    width: 80px;
    height: 6px;
    background-color: var(--color-bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
  }

  .confidence-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s;
  }

  .confidence-value {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    width: 2.5rem;
    text-align: right;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }
</style>
