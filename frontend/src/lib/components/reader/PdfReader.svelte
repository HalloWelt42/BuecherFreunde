<script>
  import * as pdfjsLib from "pdfjs-dist";
  import { dateiUrl } from "../../api/books.js";
  import { speichereLeseposition } from "../../api/user-data.js";
  import { getToken } from "../../api/client.js";
  import { onMount, onDestroy } from "svelte";

  let {
    bookId,
    initialPage = 1,
    onPositionChange = () => {},
  } = $props();

  let scrollContainer = $state(null);
  let pdfDoc = $state(null);
  let totalPages = $state(0);
  let currentPage = $state(initialPage);
  let scale = $state(1.0);
  let laden = $state(true);
  let fehler = $state(null);

  // Papier-Modus: "normal", "dunkel", "sepia", "kontrast"
  let papierModus = $state("normal");

  // Seiten-Canvases
  let pageElements = $state([]);
  let renderedPages = new Set();
  let renderQueue = new Set();
  let observer = null;

  // Worker lokal buendeln
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
  ).href;

  // Zoom-Stufen
  const ZOOM_STUFEN = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0];

  function naechsterZoom(richtung) {
    const idx = ZOOM_STUFEN.findIndex((z) => z >= scale);
    if (richtung > 0) {
      const next = idx < ZOOM_STUFEN.length - 1 ? idx + 1 : idx;
      return ZOOM_STUFEN[next];
    } else {
      const prev = idx > 0 ? idx - 1 : 0;
      return ZOOM_STUFEN[prev];
    }
  }

  $effect(() => {
    ladePdf(bookId);
  });

  async function ladePdf(id) {
    laden = true;
    fehler = null;
    renderedPages = new Set();
    renderQueue = new Set();
    try {
      const url = dateiUrl(id);
      const loadingTask = pdfjsLib.getDocument({
        url,
        httpHeaders: { Authorization: `Bearer ${getToken()}` },
      });
      pdfDoc = await loadingTask.promise;
      totalPages = pdfDoc.numPages;
      currentPage = Math.min(initialPage, totalPages);

      // Platzhalter fuer alle Seiten erstellen
      pageElements = new Array(totalPages).fill(null);
    } catch (e) {
      fehler = e.message || "PDF konnte nicht geladen werden";
    } finally {
      laden = false;
    }
  }

  // IntersectionObserver fuer Lazy-Rendering
  function setupObserver() {
    if (observer) observer.disconnect();
    if (!scrollContainer) return;

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const pageNum = Number(entry.target.dataset.page);
          if (entry.isIntersecting) {
            renderPageIfNeeded(pageNum);
            // Auch Nachbarseiten vorladen
            if (pageNum > 1) renderPageIfNeeded(pageNum - 1);
            if (pageNum < totalPages) renderPageIfNeeded(pageNum + 1);
          }
        }

        // Aktuelle Seite bestimmen (oberste sichtbare)
        const visible = entries
          .filter((e) => e.isIntersecting)
          .map((e) => Number(e.target.dataset.page))
          .sort((a, b) => a - b);
        if (visible.length > 0 && visible[0] !== currentPage) {
          currentPage = visible[0];
          savePosition();
        }
      },
      { root: scrollContainer, rootMargin: "200px 0px" },
    );

    // Alle Seiten-Wrapper beobachten
    const wrappers = scrollContainer.querySelectorAll(".page-wrapper");
    for (const w of wrappers) {
      observer.observe(w);
    }
  }

  async function renderPageIfNeeded(pageNum) {
    if (renderedPages.has(pageNum) || renderQueue.has(pageNum) || !pdfDoc) return;
    renderQueue.add(pageNum);

    try {
      const page = await pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale });
      const wrapper = scrollContainer?.querySelector(`[data-page="${pageNum}"]`);
      if (!wrapper) return;

      let canvas = wrapper.querySelector("canvas");
      if (!canvas) {
        canvas = document.createElement("canvas");
        // Vorherige Inhalte loeschen
        wrapper.innerHTML = "";
        wrapper.appendChild(canvas);
      }

      const ctx = canvas.getContext("2d");
      const dpr = window.devicePixelRatio || 1;
      canvas.width = viewport.width * dpr;
      canvas.height = viewport.height * dpr;
      canvas.style.width = viewport.width + "px";
      canvas.style.height = viewport.height + "px";
      ctx.scale(dpr, dpr);

      await page.render({ canvasContext: ctx, viewport }).promise;
      renderedPages.add(pageNum);
    } catch {
      // Seite konnte nicht gerendert werden
    } finally {
      renderQueue.delete(pageNum);
    }
  }

  // Bei Scale-Aenderung alle Seiten neu rendern
  async function reRenderAll() {
    if (!pdfDoc || !scrollContainer) return;
    renderedPages = new Set();
    renderQueue = new Set();

    // Wrapper-Groessen aktualisieren
    for (let i = 1; i <= totalPages; i++) {
      const wrapper = scrollContainer.querySelector(`[data-page="${i}"]`);
      if (wrapper) {
        const page = await pdfDoc.getPage(i);
        const viewport = page.getViewport({ scale });
        wrapper.style.width = viewport.width + "px";
        wrapper.style.height = viewport.height + "px";
        // Canvas leeren
        const canvas = wrapper.querySelector("canvas");
        if (canvas) canvas.remove();
      }
    }

    // Observer neu aufsetzen -> rendert sichtbare Seiten
    setupObserver();
  }

  // Seiten-Dimensionen ermitteln fuer Platzhalter
  async function getPageDimensions(pageNum) {
    if (!pdfDoc) return { width: 600, height: 800 };
    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale });
    return { width: viewport.width, height: viewport.height };
  }

  function zoomIn() {
    scale = naechsterZoom(1);
    reRenderAll();
  }

  function zoomOut() {
    scale = naechsterZoom(-1);
    reRenderAll();
  }

  function setZoom(newScale) {
    scale = newScale;
    reRenderAll();
  }

  function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    const wrapper = scrollContainer?.querySelector(`[data-page="${page}"]`);
    if (wrapper) {
      wrapper.scrollIntoView({ behavior: "auto", block: "start" });
    }
    savePosition();
  }

  function togglePapierModus() {
    const modi = ["normal", "sepia", "dunkel", "kontrast"];
    const idx = modi.indexOf(papierModus);
    papierModus = modi[(idx + 1) % modi.length];
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
    }, 1500);
  }

  function handleKeydown(event) {
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      zoomIn();
    } else if (event.key === "-") {
      event.preventDefault();
      zoomOut();
    }
  }

  // Observer aufsetzen wenn PDF geladen und Container bereit
  $effect(() => {
    if (!laden && pdfDoc && scrollContainer && totalPages > 0) {
      // Kurz warten bis DOM gerendert ist
      requestAnimationFrame(() => {
        setupObserver();
        // Zur Startseite scrollen
        if (initialPage > 1) {
          setTimeout(() => goToPage(initialPage), 100);
        }
      });
    }
  });

  onDestroy(() => {
    if (observer) observer.disconnect();
    clearTimeout(saveTimeout);
  });

  // Seiten-Eingabefeld
  let pageInput = $state("");
  function handlePageInput(e) {
    if (e.key === "Enter") {
      const p = Number(pageInput);
      if (p >= 1 && p <= totalPages) {
        goToPage(p);
      }
      pageInput = "";
      e.target.blur();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="pdf-reader">
  {#if laden}
    <div class="status">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <span>PDF wird geladen...</span>
    </div>
  {:else if fehler}
    <div class="status error">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <span>{fehler}</span>
    </div>
  {:else}
    <!-- Toolbar -->
    <div class="pdf-toolbar">
      <div class="toolbar-group">
        <button
          class="tool-btn"
          onclick={() => goToPage(currentPage - 1)}
          disabled={currentPage <= 1}
          title="Vorherige Seite"
        >
          <i class="fa-solid fa-chevron-up"></i>
        </button>
        <div class="page-nav">
          <input
            type="text"
            class="page-input"
            placeholder={String(currentPage)}
            bind:value={pageInput}
            onkeydown={handlePageInput}
            onfocus={(e) => { pageInput = String(currentPage); e.target.select(); }}
            onblur={() => { pageInput = ""; }}
          />
          <span class="page-total">/ {totalPages}</span>
        </div>
        <button
          class="tool-btn"
          onclick={() => goToPage(currentPage + 1)}
          disabled={currentPage >= totalPages}
          title="Nächste Seite"
        >
          <i class="fa-solid fa-chevron-down"></i>
        </button>
      </div>

      <div class="toolbar-sep"></div>

      <div class="toolbar-group">
        <button class="tool-btn" onclick={zoomOut} title="Verkleinern" disabled={scale <= 0.5}>
          <i class="fa-solid fa-minus"></i>
        </button>
        <button class="zoom-display" onclick={() => setZoom(1.0)} title="Zoom zurücksetzen">
          {Math.round(scale * 100)}%
        </button>
        <button class="tool-btn" onclick={zoomIn} title="Vergrößern" disabled={scale >= 3.0}>
          <i class="fa-solid fa-plus"></i>
        </button>
      </div>

      <div class="toolbar-sep"></div>

      <div class="toolbar-group">
        <button
          class="tool-btn papier-btn"
          class:active={papierModus !== "normal"}
          onclick={togglePapierModus}
          title="Papier: {papierModus === 'normal' ? 'Normal' : papierModus === 'sepia' ? 'Sepia' : papierModus === 'dunkel' ? 'Dunkel (Bilder erhalten)' : 'Hoher Kontrast'}"
        >
          {#if papierModus === "normal"}
            <i class="fa-solid fa-sun"></i>
          {:else if papierModus === "sepia"}
            <i class="fa-solid fa-cloud-sun" style="color: #d4a574"></i>
          {:else if papierModus === "dunkel"}
            <i class="fa-solid fa-moon"></i>
          {:else}
            <i class="fa-solid fa-circle-half-stroke"></i>
          {/if}
        </button>
      </div>
    </div>

    <!-- Scroll-Container mit allen Seiten -->
    <div
      class="scroll-container"
      class:papier-sepia={papierModus === "sepia"}
      class:papier-dunkel={papierModus === "dunkel"}
      class:papier-kontrast={papierModus === "kontrast"}
      bind:this={scrollContainer}
    >
      {#each Array(totalPages) as _, i}
        <div
          class="page-wrapper"
          data-page={i + 1}
        >
          <div class="page-loading">
            <span class="page-number">{i + 1}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .pdf-reader {
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
  .pdf-toolbar {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    flex-shrink: 0;
    height: 36px;
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
    margin: 0 0.375rem;
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

  .page-nav {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .page-input {
    width: 2.5rem;
    text-align: center;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 0.125rem 0.25rem;
    font-size: 0.75rem;
    font-family: var(--font-mono);
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    height: 24px;
  }

  .page-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .page-total {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
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

  /* Scroll-Container */
  .scroll-container {
    flex: 1;
    overflow-y: auto;
    overflow-x: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 12px;
    background-color: #525659;
  }

  :global(:root.dark) .scroll-container {
    background-color: #2a2a2e;
  }

  /* Seiten-Wrapper */
  .page-wrapper {
    position: relative;
    background-color: #fff;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    min-width: 200px;
    min-height: 280px;
    flex-shrink: 0;
  }

  .page-wrapper :global(canvas) {
    display: block;
  }

  /* Papier-Modi (unabhaengig vom App-Theme) */
  .papier-sepia .page-wrapper {
    background-color: #f4ecd8;
  }

  .papier-sepia .page-wrapper :global(canvas) {
    filter: sepia(0.3) brightness(0.95);
  }

  /* Dunkel: Hintergrund invertieren, Bilder erhalten (brightness+contrast statt invert) */
  .papier-dunkel .page-wrapper {
    background-color: #1e1e1e;
  }

  .papier-dunkel .page-wrapper :global(canvas) {
    filter: invert(0.88) hue-rotate(180deg) brightness(1.1);
  }

  /* Hoher Kontrast: Volle Invertierung */
  .papier-kontrast .page-wrapper {
    background-color: #111;
  }

  .papier-kontrast .page-wrapper :global(canvas) {
    filter: invert(1) hue-rotate(180deg);
  }

  .page-loading {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .page-number {
    font-size: 0.75rem;
    color: #999;
    font-family: var(--font-mono);
  }
</style>
