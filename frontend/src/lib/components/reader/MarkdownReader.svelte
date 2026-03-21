<script>
  import { dateiUrl } from "../../api/books.js";
  import { getToken } from "../../api/client.js";
  import { speichereLeseposition } from "../../api/user-data.js";
  import { ui } from "../../stores/ui.svelte.js";

  let {
    bookId,
    title = "",
    initialPapier = "",
    initialFontSize = 0,
    initialScrollPct = 0,
    onBack = () => {},
    onPositionChange = () => {},
  } = $props();

  let content = $state("");
  let laden = $state(true);
  let fehler = $state(null);
  let fontSize = $state(initialFontSize > 0 ? initialFontSize : 100);
  let scrollContainer = $state(null);

  // Geschätzte Seiten (~2000 Zeichen pro Seite)
  const ZEICHEN_PRO_SEITE = 2000;
  let geschaetzteSeiten = $derived(Math.max(1, Math.ceil(content.length / ZEICHEN_PRO_SEITE)));
  let aktuelleSeite = $state(1);
  let fortschritt = $state(0);

  // Papier-Modus
  const papierModi = ["normal", "sepia", "dunkel"];
  let papierModus = $state(papierModi.includes(initialPapier) ? initialPapier : "normal");

  function togglePapierModus() {
    const idx = papierModi.indexOf(papierModus);
    papierModus = papierModi[(idx + 1) % papierModi.length];
    triggerSave();
  }

  $effect(() => {
    ladeText(bookId);
  });

  async function ladeText(id) {
    laden = true;
    fehler = null;
    try {
      const url = dateiUrl(id);
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!response.ok) throw new Error("Datei konnte nicht geladen werden");
      content = await response.text();
      // Nach Laden zur gespeicherten Position scrollen
      if (initialScrollPct > 0) {
        requestAnimationFrame(() => {
          if (scrollContainer) {
            const scrollMax = scrollContainer.scrollHeight - scrollContainer.clientHeight;
            scrollContainer.scrollTop = (initialScrollPct / 100) * scrollMax;
          }
        });
      }
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  function changeFontSize(delta) {
    fontSize = Math.max(50, Math.min(200, fontSize + delta));
    triggerSave();
  }

  // Alle Einstellungen speichern
  function triggerSave() {
    clearTimeout(saveTimeout);
    // URL sofort
    const params = new URLSearchParams();
    if (fortschritt > 0) params.set("pos", String(fortschritt));
    if (papierModus !== "normal") params.set("papier", papierModus);
    if (fontSize !== 100) params.set("font", String(fontSize));
    const newUrl = `/book/${bookId}/read${params.toString() ? "?" + params.toString() : ""}`;
    history.replaceState(null, "", newUrl);

    saveTimeout = setTimeout(async () => {
      const settings = {
        scrollPct: fortschritt,
        papier: papierModus,
        fontSize,
      };
      const pos = `txt:${JSON.stringify(settings)}`;
      onPositionChange(pos);
      try {
        await speichereLeseposition(bookId, pos);
      } catch { /* still */ }
    }, 1500);
  }

  function downloadFile() {
    const a = document.createElement("a");
    a.href = dateiUrl(bookId);
    a.download = title || `buch-${bookId}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // Leseposition tracken
  let saveTimeout;
  function handleScroll() {
    if (!scrollContainer) return;
    const scrollMax = scrollContainer.scrollHeight - scrollContainer.clientHeight;
    if (scrollMax <= 0) return;
    const pct = scrollContainer.scrollTop / scrollMax;
    fortschritt = Math.round(pct * 100);
    aktuelleSeite = Math.max(1, Math.min(geschaetzteSeiten, Math.ceil(pct * geschaetzteSeiten) || 1));
    triggerSave();
  }
</script>

<div class="md-reader">
  {#if laden}
    <div class="status">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <span>Text wird geladen...</span>
    </div>
  {:else if fehler}
    <div class="status error">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <span>{fehler}</span>
    </div>
  {:else}
    <div class="md-toolbar">
      <button class="tool-btn" onclick={onBack} title="Zurück">
        <i class="fa-solid fa-arrow-left"></i>
      </button>
      <span class="toolbar-title" title={title}>{title}</span>

      <div class="toolbar-sep"></div>

      <!-- Geschätzte Seitenposition -->
      <div class="toolbar-group">
        <span class="page-info">~{aktuelleSeite} / {geschaetzteSeiten}</span>
        <span class="progress-info">{fortschritt}%</span>
      </div>

      <div class="toolbar-sep"></div>

      <!-- Schriftgröße -->
      <div class="toolbar-group">
        <button class="tool-btn" onclick={() => changeFontSize(-10)} title="Schrift kleiner" disabled={fontSize <= 50}>
          <i class="fa-solid fa-minus"></i>
        </button>
        <button class="zoom-display" onclick={() => { fontSize = 100; }} title="Schriftgröße zurücksetzen">
          {fontSize}%
        </button>
        <button class="tool-btn" onclick={() => changeFontSize(10)} title="Schrift größer" disabled={fontSize >= 200}>
          <i class="fa-solid fa-plus"></i>
        </button>
      </div>

      <div class="toolbar-sep"></div>

      <!-- Papier-Modus -->
      <button
        class="tool-btn"
        class:active={papierModus !== "normal"}
        onclick={togglePapierModus}
        title="Papier: {papierModus === 'normal' ? 'Normal' : papierModus === 'sepia' ? 'Sepia' : 'Dunkel'}"
      >
        {#if papierModus === "normal"}
          <i class="fa-solid fa-sun"></i>
        {:else if papierModus === "sepia"}
          <i class="fa-solid fa-cloud-sun" style="color: #d4a574"></i>
        {:else}
          <i class="fa-solid fa-moon"></i>
        {/if}
      </button>

      <div class="toolbar-spacer"></div>

      <button class="tool-btn" class:active={ui.readerFullscreen} onclick={() => ui.toggleReaderFullscreen()} title="{ui.readerFullscreen ? 'Vollbild verlassen' : 'Vollbild'}">
        <i class="fa-solid {ui.readerFullscreen ? 'fa-compress' : 'fa-expand'}"></i>
      </button>
      <button class="tool-btn" onclick={downloadFile} title="Herunterladen">
        <i class="fa-solid fa-download"></i>
      </button>
    </div>

    <div
      class="text-content"
      class:papier-sepia={papierModus === "sepia"}
      class:papier-dunkel={papierModus === "dunkel"}
      bind:this={scrollContainer}
      onscroll={handleScroll}
    >
      <pre class="text-pre" style="font-size: {fontSize}%">{content}</pre>
    </div>
  {/if}
</div>

<style>
  .md-reader {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }

  .status {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: 0.75rem;
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }

  .status.error {
    color: var(--color-error);
  }

  /* Toolbar */
  .md-toolbar {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    flex-shrink: 0;
    height: 36px;
  }

  .toolbar-title {
    font-weight: 600;
    font-size: 0.8125rem;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 240px;
  }

  .toolbar-spacer {
    flex: 1;
  }

  .toolbar-group {
    display: flex;
    align-items: center;
    gap: 0.125rem;
  }

  .toolbar-sep {
    width: 1px;
    height: 20px;
    background-color: var(--color-border);
    margin: 0 0.25rem;
  }

  .tool-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 0.75rem;
    transition: background-color 0.1s;
  }

  .tool-btn:hover:not(:disabled) {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .tool-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .tool-btn.active {
    background-color: var(--color-accent-light);
    color: var(--color-accent);
  }

  .page-info {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    white-space: nowrap;
  }

  .progress-info {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    min-width: 2rem;
    text-align: center;
  }

  .zoom-display {
    min-width: 3rem;
    height: 24px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    cursor: pointer;
    text-align: center;
    padding: 0 0.25rem;
  }

  .zoom-display:hover {
    background-color: var(--color-bg-tertiary);
  }

  /* Text-Inhalt */
  .text-content {
    flex: 1;
    overflow: auto;
    padding: 2rem;
    background-color: var(--color-bg-primary);
  }

  .text-content.papier-sepia {
    background-color: #f4ecd8;
  }

  :global(:root.dark) .text-content.papier-sepia {
    background-color: #3d3526;
  }

  .text-content.papier-dunkel {
    background-color: #1e1e1e;
  }

  .text-pre {
    font-family: var(--font-sans);
    line-height: 1.7;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: var(--color-text-primary);
    max-width: 800px;
    margin: 0 auto;
  }

  .papier-sepia .text-pre {
    color: #3d2b1f;
  }

  :global(:root.dark) .papier-sepia .text-pre {
    color: #d4c5a9;
  }

  .papier-dunkel .text-pre {
    color: #c8c8c8;
  }
</style>
