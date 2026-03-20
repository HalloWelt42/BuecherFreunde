<script>
  import * as pdfjsLib from "pdfjs-dist";
  import { dateiUrl } from "../../api/books.js";
  import { speichereLeseposition } from "../../api/user-data.js";
  import { getToken } from "../../api/client.js";

  let {
    bookId,
    initialPage = 1,
    onPositionChange = () => {},
  } = $props();

  let canvasEl = $state(null);
  let pdfDoc = $state(null);
  let currentPage = $state(initialPage);
  let totalPages = $state(0);
  let scale = $state(1.5);
  let laden = $state(true);
  let fehler = $state(null);
  let rendering = $state(false);

  // Worker lokal bündeln
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
  ).href;

  $effect(() => {
    ladePdf(bookId);
  });

  async function ladePdf(id) {
    laden = true;
    fehler = null;
    try {
      const url = dateiUrl(id);
      const loadingTask = pdfjsLib.getDocument({
        url,
        httpHeaders: { Authorization: `Bearer ${getToken()}` },
      });
      pdfDoc = await loadingTask.promise;
      totalPages = pdfDoc.numPages;
      currentPage = Math.min(initialPage, totalPages);
      renderPage(currentPage);
    } catch (e) {
      fehler = e.message || "PDF konnte nicht geladen werden";
    } finally {
      laden = false;
    }
  }

  async function renderPage(pageNum) {
    if (!pdfDoc || !canvasEl || rendering) return;
    rendering = true;
    try {
      const page = await pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale });
      const canvas = canvasEl;
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: ctx, viewport }).promise;
    } catch (e) {
      fehler = "Seite konnte nicht gerendert werden";
    } finally {
      rendering = false;
    }
  }

  function goToPage(page) {
    if (page < 1 || page > totalPages || page === currentPage) return;
    currentPage = page;
    renderPage(currentPage);
    savePosition();
  }

  function zoomIn() {
    scale = Math.min(scale + 0.25, 4);
    renderPage(currentPage);
  }

  function zoomOut() {
    scale = Math.max(scale - 0.25, 0.5);
    renderPage(currentPage);
  }

  let saveTimeout;
  function savePosition() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(async () => {
      const pos = `page:${currentPage}`;
      onPositionChange(pos);
      try {
        await speichereLeseposition(bookId, pos);
      } catch { /* still */ }
    }, 1000);
  }

  function handleKeydown(event) {
    if (event.key === "ArrowRight" || event.key === "PageDown") {
      goToPage(currentPage + 1);
    } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
      goToPage(currentPage - 1);
    } else if (event.key === "+" || event.key === "=") {
      zoomIn();
    } else if (event.key === "-") {
      zoomOut();
    }
  }

  // Reaktion auf scale-Änderung
  $effect(() => {
    if (pdfDoc && canvasEl && !laden) {
      renderPage(currentPage);
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="pdf-reader">
  {#if laden}
    <div class="status">PDF wird geladen...</div>
  {:else if fehler}
    <div class="status error">{fehler}</div>
  {:else}
    <div class="toolbar">
      <button onclick={() => goToPage(currentPage - 1)} disabled={currentPage <= 1}>
        &larr;
      </button>
      <span class="page-info">
        <input
          type="number"
          class="page-input"
          min="1"
          max={totalPages}
          value={currentPage}
          onchange={(e) => goToPage(Number(e.target.value))}
        />
        / {totalPages}
      </span>
      <button onclick={() => goToPage(currentPage + 1)} disabled={currentPage >= totalPages}>
        &rarr;
      </button>
      <div class="toolbar-separator"></div>
      <button onclick={zoomOut} title="Verkleinern">-</button>
      <span class="zoom-info">{Math.round(scale * 100)}%</span>
      <button onclick={zoomIn} title="Vergrößern">+</button>
    </div>

    <div class="canvas-container">
      <canvas bind:this={canvasEl} class="pdf-canvas"></canvas>
    </div>
  {/if}
</div>

<style>
  .pdf-reader {
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

  .toolbar button:hover:not(:disabled) {
    background-color: var(--color-bg-tertiary);
  }

  .toolbar button:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .page-info {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
  }

  .page-input {
    width: 3rem;
    text-align: center;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 0.125rem;
    font-size: 0.875rem;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
  }

  .toolbar-separator {
    width: 1px;
    height: 1.5rem;
    background-color: var(--color-border);
  }

  .zoom-info {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    min-width: 3rem;
    text-align: center;
  }

  .canvas-container {
    flex: 1;
    overflow: auto;
    display: flex;
    justify-content: center;
    padding: 1rem;
    background-color: var(--color-bg-tertiary);
  }

  .pdf-canvas {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }

  :global(:root.dark) .pdf-canvas {
    filter: invert(1) hue-rotate(180deg);
  }
</style>
