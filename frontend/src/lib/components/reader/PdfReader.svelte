<script>
  import * as pdfjsLib from "pdfjs-dist";
  import "pdfjs-dist/web/pdf_viewer.css";
  const { TextLayer } = pdfjsLib;
  import { dateiUrl } from "../../api/books.js";
  import { speichereLeseposition } from "../../api/user-data.js";
  import { getToken } from "../../api/client.js";
  import { ui } from "../../stores/ui.svelte.js";
  import { onMount, onDestroy, untrack } from "svelte";
  import { createSwipeHandler } from "../../utils/touch.js";
  import { highlightsFuerBuch, erstelleHighlight, aktualisiereHighlight, loescheHighlight } from "../../api/highlights.js";
  import TextSelectionMenu from "./TextSelectionMenu.svelte";
  import ReaderHighlights from "./ReaderHighlights.svelte";
  import ReaderNotes from "./ReaderNotes.svelte";

  let {
    bookId,
    title = "",
    initialPage = 1,
    initialAnsicht = "",
    initialPapier = "",
    initialZoom = 0,
    onBack = () => {},
    onPositionChange = () => {},
  } = $props();

  let scrollContainer = $state(null);
  let pdfDoc = $state(null);
  let totalPages = $state(0);
  let currentPage = $state(untrack(() => initialPage));
  let scale = $state(untrack(() => initialZoom > 0 ? initialZoom / 100 : 1.0));
  let laden = $state(true);
  let fehler = $state(null);

  // Papier-Modus: "normal", "dunkel", "sepia", "kontrast"
  const gueltigePapierModi = ["normal", "sepia", "dunkel", "kontrast"];
  let papierModus = $state(untrack(() =>
    gueltigePapierModi.includes(initialPapier) ? initialPapier : "normal"
  ));

  // Ansichtsmodus: "scroll", "breite", "seite", "doppel", "einzeln"
  const gueltigeAnsichten = ["scroll", "breite", "seite", "doppel", "einzeln"];
  let ansicht = $state(untrack(() =>
    gueltigeAnsichten.includes(initialAnsicht) ? initialAnsicht : "scroll"
  ));

  // Seiten-Canvases
  let pageElements = $state([]);
  let renderedPages = new Set();
  let renderQueue = new Set();
  let observer = null;
  let _baseViewport = null;

  // Highlights
  let highlights = $state([]);
  let highlighterActive = $state(false);
  let highlightsReloadTrigger = $state(0);

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

  // Scale berechnen fuer Breite/Seite einpassen
  function berechneAutoScale(modus) {
    if (!_baseViewport || !scrollContainer) return 1.0;
    const containerW = scrollContainer.clientWidth - 24;
    const containerH = scrollContainer.clientHeight - 24;
    const pageW = _baseViewport.width;
    const pageH = _baseViewport.height;

    if (modus === "breite") {
      const targetW = (ansicht === "doppel") ? (containerW - 16) / 2 : containerW;
      return targetW / pageW;
    } else if (modus === "seite") {
      const scaleW = containerW / pageW;
      const scaleH = containerH / pageH;
      return Math.min(scaleW, scaleH);
    } else if (modus === "doppel") {
      const scaleW = (containerW - 16) / (pageW * 2);
      const scaleH = containerH / pageH;
      return Math.min(scaleW, scaleH);
    }
    return 1.0;
  }

  $effect(() => {
    ladePdf(bookId);
  });

  // Touch-Swipe fuer iPad/Tablets: nur bei Einzel-/Doppel-Ansicht
  $effect(() => {
    if (!scrollContainer || ansicht === "scroll") return;
    const cleanup = createSwipeHandler(scrollContainer, {
      onSwipeLeft: () => nextPage(),
      onSwipeRight: () => prevPage(),
    });
    return cleanup;
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

      const page1 = await pdfDoc.getPage(1);
      _baseViewport = page1.getViewport({ scale: 1.0 });

      pageElements = new Array(totalPages).fill(null);

      // Highlights laden
      await ladeHighlights();
    } catch (e) {
      fehler = e.message || "PDF konnte nicht geladen werden";
    } finally {
      laden = false;
    }
  }

  // Highlights laden
  async function ladeHighlights() {
    try {
      highlights = await highlightsFuerBuch(bookId);
    } catch {
      highlights = [];
    }
  }

  async function speichereHighlight(pageNum, text, color) {
    if (!text) return;
    // Tatsaechliche Seite aus der Selektion ermitteln
    const actualPage = getSelectionPage() || pageNum;
    try {
      const hl = await erstelleHighlight(bookId, {
        cfi_range: `page:${actualPage}`,
        color,
        text_snippet: text.slice(0, 300),
      });
      highlights = [...highlights, hl];
      highlightsReloadTrigger++;
      renderAllVisibleHighlights();
    } catch {}
  }

  // Ermittelt die Seitennummer aus der aktuellen Textselektion
  function getSelectionPage() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return null;
    const node = sel.anchorNode;
    if (!node) return null;
    const wrapper = node.nodeType === Node.ELEMENT_NODE
      ? node.closest(".page-wrapper")
      : node.parentElement?.closest(".page-wrapper");
    if (wrapper) return Number(wrapper.dataset.page);
    return null;
  }

  async function onHighlightUpdate(hlId, daten) {
    try {
      await aktualisiereHighlight(hlId, daten);
      highlights = highlights.map(h => h.id === hlId ? { ...h, ...daten } : h);
      highlightsReloadTrigger++;
      renderAllVisibleHighlights();
    } catch {}
  }

  async function onHighlightDelete(hlId) {
    try {
      await loescheHighlight(hlId);
      highlights = highlights.filter(h => h.id !== hlId);
      highlightsReloadTrigger++;
      renderAllVisibleHighlights();
    } catch {}
  }

  // Highlights visuell auf TextLayer-Spans rendern
  function renderHighlightsForPage(pageNum, textDiv) {
    if (!textDiv) return;

    const spans = Array.from(textDiv.querySelectorAll("span"));
    if (spans.length === 0) return;

    const pageHighlights = highlights.filter(h => h.cfi_range === `page:${pageNum}`);
    if (pageHighlights.length === 0) return;

    for (const hl of pageHighlights) {
      const snippet = (hl.text_snippet || "").trim();
      if (!snippet || snippet.length < 2) continue;

      // Farbe mit Alpha fuer sichtbares Highlight
      const color = hl.color || "#ffeb3b";
      const bgColor = hexToRgba(color, 0.35);

      // Strategie: Zusammenhaengenden Text aus Spans aufbauen und Snippet darin finden
      const spanTexts = spans.map(s => s.textContent || "");
      const fullText = spanTexts.join("");

      // Normalisierte Suche (Whitespace zusammenfassen)
      const normalSnippet = snippet.replace(/\s+/g, " ");
      const normalFull = fullText.replace(/\s+/g, " ");
      const matchIdx = normalFull.indexOf(normalSnippet);

      if (matchIdx === -1) {
        // Fallback: ersten 30 Zeichen suchen fuer partielle Treffer
        const shortSnippet = normalSnippet.substring(0, Math.min(30, normalSnippet.length));
        const shortIdx = normalFull.indexOf(shortSnippet);
        if (shortIdx === -1) continue;
        markSpansInRange(spans, spanTexts, shortIdx, shortIdx + normalSnippet.length, bgColor, hl.id);
      } else {
        markSpansInRange(spans, spanTexts, matchIdx, matchIdx + normalSnippet.length, bgColor, hl.id);
      }
    }
  }

  // Spans im Zeichenbereich [startChar, endChar) markieren
  function markSpansInRange(spans, spanTexts, startChar, endChar, bgColor, hlId) {
    let charPos = 0;
    for (let i = 0; i < spans.length; i++) {
      const text = spanTexts[i];
      const spanStart = charPos;
      const spanEnd = charPos + text.length;
      charPos = spanEnd;

      // Span ueberlappt mit dem Highlight-Bereich?
      if (spanEnd > startChar && spanStart < endChar && text.trim().length > 0) {
        spans[i].style.backgroundColor = bgColor;
        spans[i].style.borderRadius = "2px";
        spans[i].dataset.highlightId = String(hlId);
      }
    }
  }

  function hexToRgba(hex, alpha) {
    const h = hex.replace("#", "");
    const r = parseInt(h.substring(0, 2), 16);
    const g = parseInt(h.substring(2, 4), 16);
    const b = parseInt(h.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function renderAllVisibleHighlights() {
    if (!scrollContainer) return;
    const wrappers = scrollContainer.querySelectorAll(".page-wrapper");
    for (const w of wrappers) {
      const textDiv = w.querySelector(".textLayer");
      if (!textDiv) continue;
      const pageNum = Number(w.dataset.page);
      // Erst alte Highlight-Styles entfernen
      const spans = textDiv.querySelectorAll("span[data-highlight-id]");
      for (const s of spans) {
        s.style.backgroundColor = "";
        s.style.borderRadius = "";
        delete s.dataset.highlightId;
      }
      // Neu rendern
      renderHighlightsForPage(pageNum, textDiv);
    }
  }

  // IntersectionObserver fuer Lazy-Rendering (nur im Scroll-Modus)
  function setupObserver() {
    if (observer) observer.disconnect();
    if (!scrollContainer) return;
    if (ansicht === "einzeln" || ansicht === "doppel") return;

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const pageNum = Number(entry.target.dataset.page);
          if (entry.isIntersecting) {
            renderPageIfNeeded(pageNum);
            if (pageNum > 1) renderPageIfNeeded(pageNum - 1);
            if (pageNum < totalPages) renderPageIfNeeded(pageNum + 1);
          }
        }

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

    const wrappers = scrollContainer.querySelectorAll(".page-wrapper");
    for (const w of wrappers) {
      observer.observe(w);
    }
  }

  async function renderPageIfNeeded(pageNum) {
    if (renderedPages.has(pageNum) || renderQueue.has(pageNum) || !pdfDoc) return;
    if (pageNum < 1 || pageNum > totalPages) return;
    renderQueue.add(pageNum);

    try {
      const page = await pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale });
      const wrapper = scrollContainer?.querySelector(`[data-page="${pageNum}"]`);
      if (!wrapper) return;

      // Canvas erstellen/aktualisieren
      let canvas = wrapper.querySelector("canvas");
      if (!canvas) {
        canvas = document.createElement("canvas");
        // Alte Inhalte entfernen, aber page-loading behalten bis Canvas fertig
        const loading = wrapper.querySelector(".page-loading");
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

      // TextLayer erstellen
      let textDiv = wrapper.querySelector(".textLayer");
      if (textDiv) textDiv.remove();
      textDiv = document.createElement("div");
      textDiv.className = "textLayer";
      textDiv.style.width = viewport.width + "px";
      textDiv.style.height = viewport.height + "px";
      // pdfjs CSS benoetigt --total-scale-factor fuer korrekte Schriftgroesse
      textDiv.style.setProperty("--total-scale-factor", String(scale));
      wrapper.appendChild(textDiv);

      const textContent = await page.getTextContent();
      const textLayer = new TextLayer({
        textContentSource: textContent,
        container: textDiv,
        viewport,
      });
      await textLayer.render();

      // Highlights fuer diese Seite rendern
      renderHighlightsForPage(pageNum, textDiv);

      // Wrapper-Groesse setzen
      wrapper.style.width = viewport.width + "px";
      wrapper.style.height = viewport.height + "px";

      renderedPages.add(pageNum);
    } catch (err) {
      console.error(`Seite ${pageNum} Render-Fehler:`, err);
    } finally {
      renderQueue.delete(pageNum);
    }
  }

  // Bei Scale-Aenderung alle Seiten neu rendern
  async function reRenderAll() {
    if (!pdfDoc || !scrollContainer) return;
    renderedPages = new Set();
    renderQueue = new Set();

    if (ansicht === "einzeln" || ansicht === "doppel") {
      await renderEinzelSeiten();
      return;
    }

    // Scroll-Modus: Wrapper-Groessen aktualisieren
    for (let i = 1; i <= totalPages; i++) {
      const wrapper = scrollContainer.querySelector(`[data-page="${i}"]`);
      if (wrapper) {
        const page = await pdfDoc.getPage(i);
        const viewport = page.getViewport({ scale });
        wrapper.style.width = viewport.width + "px";
        wrapper.style.height = viewport.height + "px";
        const canvas = wrapper.querySelector("canvas");
        if (canvas) canvas.remove();
        const textLayer = wrapper.querySelector(".textLayer");
        if (textLayer) textLayer.remove();
      }
    }

    setupObserver();
  }

  // Einzelseiten/Doppelseiten rendern
  async function renderEinzelSeiten() {
    if (!pdfDoc || !scrollContainer) return;
    renderedPages = new Set();
    renderQueue = new Set();

    const wrappers = scrollContainer.querySelectorAll(".page-wrapper");
    for (const w of wrappers) {
      const canvas = w.querySelector("canvas");
      if (canvas) canvas.remove();
      const textLayer = w.querySelector(".textLayer");
      if (textLayer) textLayer.remove();
    }

    if (ansicht === "einzeln") {
      await renderPageIfNeeded(currentPage);
    } else if (ansicht === "doppel") {
      const leftPage = currentPage % 2 === 0 ? currentPage - 1 : currentPage;
      const rightPage = leftPage + 1;
      if (leftPage >= 1) await renderPageIfNeeded(leftPage);
      if (rightPage <= totalPages) await renderPageIfNeeded(rightPage);
    }
  }

  function zoomIn() {
    ansicht = "scroll";
    scale = naechsterZoom(1);
    reRenderAll();
    savePosition();
  }

  function zoomOut() {
    ansicht = "scroll";
    scale = naechsterZoom(-1);
    reRenderAll();
    savePosition();
  }

  function setZoom(newScale) {
    ansicht = "scroll";
    scale = newScale;
    reRenderAll();
    savePosition();
  }

  function setAnsicht(modus) {
    ansicht = modus;
    if (modus === "breite" || modus === "seite") {
      scale = berechneAutoScale(modus);
      reRenderAll();
    } else if (modus === "doppel") {
      scale = berechneAutoScale("doppel");
      reRenderAll();
    } else if (modus === "einzeln") {
      scale = berechneAutoScale("seite");
      reRenderAll();
    } else {
      reRenderAll();
    }
    savePosition();
  }

  function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;

    if (ansicht === "einzeln" || ansicht === "doppel") {
      renderEinzelSeiten();
    } else {
      const wrapper = scrollContainer?.querySelector(`[data-page="${page}"]`);
      if (wrapper) {
        wrapper.scrollIntoView({ behavior: "auto", block: "start" });
      }
    }
    savePosition();
  }

  function prevPage() {
    if (ansicht === "doppel") {
      goToPage(Math.max(1, currentPage - 2));
    } else {
      goToPage(currentPage - 1);
    }
  }

  function nextPage() {
    if (ansicht === "doppel") {
      goToPage(Math.min(totalPages, currentPage + 2));
    } else {
      goToPage(currentPage + 1);
    }
  }

  function togglePapierModus() {
    const modi = ["normal", "sepia", "dunkel", "kontrast"];
    const idx = modi.indexOf(papierModus);
    papierModus = modi[(idx + 1) % modi.length];
    savePosition();
  }

  // Sichtbare Seiten im Einzeln/Doppel-Modus
  let sichtbareSeiten = $derived.by(() => {
    if (ansicht === "einzeln") {
      return [currentPage];
    } else if (ansicht === "doppel") {
      const left = currentPage % 2 === 0 ? currentPage - 1 : currentPage;
      const right = left + 1;
      const pages = [];
      if (left >= 1) pages.push(left);
      if (right <= totalPages) pages.push(right);
      return pages;
    }
    return null;
  });

  // Fortschritt
  let fortschritt = $derived(totalPages > 0 ? Math.round(currentPage / totalPages * 100) : 0);

  // URL aktualisieren
  function updateUrl() {
    const params = new URLSearchParams();
    if (currentPage > 1) params.set("page", String(currentPage));
    if (ansicht !== "scroll") params.set("ansicht", ansicht);
    if (ansicht === "scroll" && scale !== 1.0) params.set("zoom", String(Math.round(scale * 100)));
    if (papierModus !== "normal") params.set("papier", papierModus);
    const qs = params.toString();
    const newUrl = `/book/${bookId}/read${qs ? "?" + qs : ""}`;
    history.replaceState(null, "", newUrl);
  }

  let saveTimeout;
  function savePosition() {
    clearTimeout(saveTimeout);
    updateUrl();
    saveTimeout = setTimeout(async () => {
      const settings = {
        page: currentPage,
        ansicht,
        zoom: Math.round(scale * 100),
        papier: papierModus,
      };
      const pos = `pdf:${JSON.stringify(settings)}`;
      onPositionChange(pos);
      try {
        await speichereLeseposition(bookId, pos);
      } catch {}
    }, 1500);
  }

  function handleKeydown(event) {
    if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") return;
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      zoomIn();
    } else if (event.key === "-") {
      event.preventDefault();
      zoomOut();
    } else if (event.key === "ArrowRight" || event.key === "PageDown") {
      event.preventDefault();
      nextPage();
    } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
      event.preventDefault();
      prevPage();
    } else if (event.key === "Home") {
      event.preventDefault();
      goToPage(1);
    } else if (event.key === "End") {
      event.preventDefault();
      goToPage(totalPages);
    } else if (event.key === "Escape" && ui.readerFullscreen) {
      event.preventDefault();
      ui.readerFullscreen = false;
    }
  }

  // Observer aufsetzen wenn PDF geladen und Container bereit
  $effect(() => {
    if (!laden && pdfDoc && scrollContainer && totalPages > 0) {
      requestAnimationFrame(() => {
        if (ansicht !== "scroll") {
          const modus = ansicht === "einzeln" ? "seite" : ansicht;
          scale = berechneAutoScale(modus);
        }

        if (ansicht === "einzeln" || ansicht === "doppel") {
          renderEinzelSeiten();
        } else {
          setupObserver();
        }
        if (initialPage > 1) {
          setTimeout(() => goToPage(initialPage), 100);
        }
      });
    }
  });

  // Bei Fenster-Resize Auto-Scale neu berechnen
  function handleResize() {
    if (ansicht === "breite" || ansicht === "seite" || ansicht === "doppel" || ansicht === "einzeln") {
      const modus = ansicht === "einzeln" ? "seite" : ansicht;
      scale = berechneAutoScale(modus);
      reRenderAll();
    }
  }

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

  function downloadFile() {
    const a = document.createElement("a");
    a.href = dateiUrl(bookId);
    a.download = title || `buch-${bookId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
</script>

<svelte:window onkeydown={handleKeydown} onresize={handleResize} />

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
      <!-- Links: Zurueck + Titel -->
      <button class="tool-btn back-btn" onclick={onBack} title="Zurueck">
        <i class="fa-solid fa-arrow-left"></i>
      </button>
      <span class="toolbar-title" title={title}>{title}</span>

      <div class="toolbar-sep"></div>

      <!-- Seiten-Navigation -->
      <div class="toolbar-group">
        <button class="tool-btn" onclick={prevPage} disabled={currentPage <= 1} title="Vorherige Seite">
          <i class="fa-solid fa-chevron-left"></i>
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
        <button class="tool-btn" onclick={nextPage} disabled={currentPage >= totalPages} title="Naechste Seite">
          <i class="fa-solid fa-chevron-right"></i>
        </button>
        <span class="toolbar-progress">{fortschritt}%</span>
      </div>

      <div class="toolbar-sep"></div>

      <!-- Zoom -->
      <div class="toolbar-group">
        <button class="tool-btn" onclick={zoomOut} title="Verkleinern" disabled={scale <= 0.5}>
          <i class="fa-solid fa-minus"></i>
        </button>
        <button class="zoom-display" onclick={() => setZoom(1.0)} title="100% zuruecksetzen">
          {Math.round(scale * 100)}%
        </button>
        <button class="tool-btn" onclick={zoomIn} title="Vergroessern" disabled={scale >= 3.0}>
          <i class="fa-solid fa-plus"></i>
        </button>
      </div>

      <div class="toolbar-sep"></div>

      <!-- Ansichtsmodus -->
      <div class="toolbar-group">
        <button class="tool-btn" class:active={ansicht === "breite"} onclick={() => setAnsicht(ansicht === "breite" ? "scroll" : "breite")} title="Seitenbreite">
          <i class="fa-solid fa-arrows-left-right"></i>
        </button>
        <button class="tool-btn" class:active={ansicht === "seite"} onclick={() => setAnsicht(ansicht === "seite" ? "scroll" : "seite")} title="Ganze Seite einpassen">
          <i class="fa-solid fa-up-down-left-right"></i>
        </button>
        <button class="tool-btn" class:active={ansicht === "doppel"} onclick={() => setAnsicht(ansicht === "doppel" ? "scroll" : "doppel")} title="Doppelseite">
          <i class="fa-solid fa-book-open"></i>
        </button>
        <button class="tool-btn" class:active={ansicht === "einzeln"} onclick={() => setAnsicht(ansicht === "einzeln" ? "scroll" : "einzeln")} title="Einzelseite">
          <i class="fa-solid fa-file"></i>
        </button>
      </div>

      <div class="toolbar-sep"></div>

      <!-- Papier-Modus -->
      <button
        class="tool-btn"
        class:active={papierModus !== "normal"}
        onclick={togglePapierModus}
        title="Papier: {papierModus === 'normal' ? 'Normal' : papierModus === 'sepia' ? 'Sepia' : papierModus === 'dunkel' ? 'Dunkel' : 'Kontrast'}"
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

      <!-- Highlighter Toggle -->
      <button
        class="tool-btn"
        class:active={highlighterActive}
        class:highlighter-on={highlighterActive}
        onclick={() => { highlighterActive = !highlighterActive; }}
        title={highlighterActive ? "Markierstift aus" : "Markierstift an"}
      >
        <i class="fa-solid fa-highlighter"></i>
      </button>

      <!-- Highlights Panel -->
      <ReaderHighlights
        {bookId}
        {highlights}
        reloadTrigger={highlightsReloadTrigger}
        onNavigate={(hl) => {
          const m = hl.cfi_range?.match(/page:(\d+)/);
          if (m) goToPage(Number(m[1]));
        }}
        onUpdate={onHighlightUpdate}
        onDelete={onHighlightDelete}
      />

      <!-- Buchnotizen Panel -->
      <ReaderNotes
        {bookId}
        positionLabel={"S." + currentPage}
      />

      <!-- Rechts: Vollbild + Download -->
      <div class="toolbar-spacer"></div>
      <button class="tool-btn" class:active={ui.readerFullscreen} onclick={() => ui.toggleReaderFullscreen()} title="{ui.readerFullscreen ? 'Vollbild verlassen' : 'Vollbild'}">
        <i class="fa-solid {ui.readerFullscreen ? 'fa-compress' : 'fa-expand'}"></i>
      </button>
      <button class="tool-btn" onclick={downloadFile} title="Herunterladen">
        <i class="fa-solid fa-download"></i>
      </button>
    </div>

    <!-- Scroll-Container -->
    <div
      class="scroll-container"
      class:papier-sepia={papierModus === "sepia"}
      class:papier-dunkel={papierModus === "dunkel"}
      class:papier-kontrast={papierModus === "kontrast"}
      class:modus-einzeln={ansicht === "einzeln"}
      class:modus-doppel={ansicht === "doppel"}
      bind:this={scrollContainer}
    >
      {#if ansicht === "einzeln" || ansicht === "doppel"}
        <div class="page-spread" class:doppel={ansicht === "doppel"}>
          {#each sichtbareSeiten as pageNum (pageNum)}
            <div class="page-wrapper" data-page={pageNum}>
              <div class="page-loading">
                <span class="page-number">{pageNum}</span>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        {#each Array(totalPages) as _, i}
          <div class="page-wrapper" data-page={i + 1}>
            <div class="page-loading">
              <span class="page-number">{i + 1}</span>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <!-- TextSelectionMenu (arbeitet mit window.getSelection auf TextLayer) -->
    <TextSelectionMenu
      {bookId}
      positionLabel={"S." + currentPage}
      {highlighterActive}
      onHighlight={(text, color) => {
        speichereHighlight(currentPage, text, color);
      }}
    />
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
    flex-wrap: wrap;
  }

  .back-btn {
    flex-shrink: 0;
  }

  .toolbar-title {
    font-weight: 600;
    font-size: 0.8125rem;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 180px;
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

  .toolbar-progress {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin-left: 0.25rem;
    min-width: 2rem;
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

  .tool-btn.highlighter-on {
    background-color: color-mix(in srgb, var(--color-warning) 20%, transparent);
    color: var(--color-warning);
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
    font-family: inherit;
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
    color: var(--color-text-primary);
    font-family: inherit;
  }

  .zoom-display {
    min-width: 3rem;
    height: 24px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    font-size: 0.75rem;
    font-family: inherit;
    color: var(--color-text-primary);
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

  .scroll-container.modus-einzeln,
  .scroll-container.modus-doppel {
    justify-content: center;
    overflow: hidden;
  }

  .page-spread {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }

  .page-spread.doppel {
    gap: 2px;
  }

  /* Seiten-Wrapper */
  .page-wrapper {
    position: relative;
    background-color: #fff;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    min-width: 200px;
    min-height: 280px;
    flex-shrink: 0;
    border-radius: 4px;
    overflow: hidden;
  }

  .page-wrapper :global(canvas) {
    display: block;
  }

  /* PDF.js TextLayer - pdfjs CSS wird importiert, hier nur Overrides */
  .page-wrapper :global(.textLayer) {
    z-index: 1;
  }

  .page-wrapper :global(.textLayer ::selection) {
    background: rgba(0, 100, 255, 0.4);
  }

  /* Papier-Modi */
  .papier-sepia .page-wrapper {
    background-color: #f4ecd8;
  }

  .papier-sepia .page-wrapper :global(canvas) {
    filter: sepia(0.3) brightness(0.95);
  }

  .papier-dunkel .page-wrapper {
    background-color: #1e1e1e;
  }

  .papier-dunkel .page-wrapper :global(canvas) {
    filter: invert(0.88) hue-rotate(180deg) brightness(1.1);
  }

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
    font-family: inherit;
  }
</style>
