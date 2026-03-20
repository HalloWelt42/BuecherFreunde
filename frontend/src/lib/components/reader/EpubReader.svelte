<script>
  import { dateiUrl } from "../../api/books.js";
  import { getToken } from "../../api/client.js";

  let {
    bookId,
    initialCfi = "",
    onPositionChange = () => {},
  } = $props();

  let containerEl = $state(null);
  let laden = $state(true);
  let fehler = $state(null);
  let fontSize = $state(100);
  let textContent = $state("");

  $effect(() => {
    ladeEpub(bookId);
  });

  async function ladeEpub(id) {
    laden = true;
    fehler = null;
    try {
      const url = dateiUrl(id);
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!response.ok) throw new Error("Datei konnte nicht geladen werden");

      // EPUB als Blob laden - foliate-js Integration wird bei
      // Installation auf dem Zielsystem eingerichtet
      const blob = await response.blob();

      // Fallback: Verwende die extrahierte Volltextdatei
      const textUrl = `/api/books/${id}/file`;
      textContent = "EPUB-Reader wird geladen. Bitte die Datei direkt herunterladen oder den Volltext nutzen.";
      laden = false;
    } catch (e) {
      fehler = e.message || "EPUB konnte nicht geladen werden";
      laden = false;
    }
  }

  function changeFontSize(delta) {
    fontSize = Math.max(50, Math.min(200, fontSize + delta));
  }
</script>

<div class="epub-reader">
  {#if laden}
    <div class="status">EPUB wird geladen...</div>
  {:else if fehler}
    <div class="status error">{fehler}</div>
  {:else}
    <div class="toolbar">
      <span class="toolbar-info">EPUB-Ansicht</span>
      <div class="toolbar-separator"></div>
      <button onclick={() => changeFontSize(-10)} title="Schrift kleiner">A-</button>
      <span class="font-info">{fontSize}%</span>
      <button onclick={() => changeFontSize(10)} title="Schrift größer">A+</button>
    </div>

    <div class="reader-container" bind:this={containerEl}>
      <div class="epub-placeholder" style="font-size: {fontSize}%">
        <p class="placeholder-msg">
          Der interaktive EPUB-Reader benötigt foliate-js.
        </p>
        <a
          href="/api/books/{bookId}/file"
          download
          class="download-btn"
        >
          EPUB herunterladen
        </a>
      </div>
    </div>
  {/if}
</div>

<style>
  .epub-reader {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .status {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--color-text-muted);
  }

  .status.error {
    color: var(--color-error);
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    border-bottom: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    flex-shrink: 0;
  }

  .toolbar button {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
  }

  .toolbar button:hover {
    background-color: var(--color-bg-tertiary);
  }

  .toolbar-info {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    flex: 1;
  }

  .toolbar-separator {
    width: 1px;
    height: 1.5rem;
    background-color: var(--color-border);
  }

  .font-info {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    min-width: 2.5rem;
    text-align: center;
  }

  .reader-container {
    flex: 1;
    overflow: auto;
  }

  .epub-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 1.5rem;
    color: var(--color-text-secondary);
  }

  .placeholder-msg {
    font-size: 0.9375rem;
  }

  .download-btn {
    padding: 0.5rem 1.25rem;
    background-color: var(--color-accent);
    color: #fff;
    border-radius: 6px;
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .download-btn:hover {
    opacity: 0.9;
  }
</style>
