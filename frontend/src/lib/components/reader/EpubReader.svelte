<script>
  import { View } from "foliate-js/view.js";
  import { dateiUrl } from "../../api/books.js";
  import { getToken } from "../../api/client.js";
  import { speichereLeseposition } from "../../api/user-data.js";
  import { onDestroy } from "svelte";

  let {
    bookId,
    title = "",
    initialCfi = "",
    initialPapier = "",
    initialFontSize = 0,
    initialFontFamily = "",
    initialLineHeight = 0,
    initialFgColor = "",
    initialBgColor = "",
    initialMaxWidthSingle = 0,
    initialMaxWidthDouble = 0,
    initialSinglePage = false,
    onBack = () => {},
    onPositionChange = () => {},
  } = $props();

  let containerEl = $state(null);
  let laden = $state(true);
  let fehler = $state(null);

  // Layout
  let maxWidthSingle = $state(initialMaxWidthSingle > 0 ? initialMaxWidthSingle : 700);
  let maxWidthDouble = $state(initialMaxWidthDouble > 0 ? initialMaxWidthDouble : 1400);
  let singlePage = $state(initialSinglePage);
  let activeMaxWidth = $derived(singlePage ? maxWidthSingle : maxWidthDouble);

  // Reader-State
  let view = null;
  let tocItems = $state([]);
  let showToc = $state(false);
  let showSettings = $state(false);
  let currentLocation = $state(null);
  let fortschritt = $state(0);

  // Verfügbare Schriften (lokal gebündelt)
  const schriften = [
    { name: "Standard", value: "" },
    { name: "Barlow", value: "Barlow, sans-serif" },
    { name: "JetBrains Mono", value: "'JetBrains Mono', monospace" },
    { name: "Serif", value: "Georgia, 'Times New Roman', serif" },
    { name: "System", value: "system-ui, -apple-system, sans-serif" },
  ];

  // Voreingestellte Farbthemen
  const farbThemen = [
    { name: "Hell", fg: "#1a1a1a", bg: "#ffffff", icon: "fa-sun" },
    { name: "Sepia", fg: "#3d2b1f", bg: "#f4ecd8", icon: "fa-cloud-sun" },
    { name: "Dämmerung", fg: "#c9b99a", bg: "#3d3526", icon: "fa-cloud-moon" },
    { name: "Dunkel", fg: "#c8c8c8", bg: "#1e1e1e", icon: "fa-moon" },
    { name: "Nacht", fg: "#8a8a8a", bg: "#0a0a0a", icon: "fa-star" },
    { name: "Individuell", fg: "", bg: "", icon: "fa-palette" },
  ];

  // Einstellungen
  let fontSize = $state(initialFontSize > 0 ? initialFontSize : 100);
  let fontFamily = $state(initialFontFamily || "");
  let lineHeight = $state(initialLineHeight > 0 ? initialLineHeight : 1.6);
  let fgColor = $state(initialFgColor || "#1a1a1a");
  let bgColor = $state(initialBgColor || "#ffffff");

  // Aktives Farbthema erkennen (Individuell = kein Preset passt)
  let activeThemeIndex = $derived.by(() => {
    const presetIdx = farbThemen.findIndex(t => t.fg && t.fg === fgColor && t.bg === bgColor);
    if (presetIdx >= 0) return presetIdx;
    // "Individuell" ist der letzte Eintrag
    return farbThemen.length - 1;
  });

  function setFarbThema(theme) {
    if (!theme.fg) return; // "Individuell" setzt nichts - Feinregler nutzen
    fgColor = theme.fg;
    bgColor = theme.bg;
    applyStyles();
    savePosition();
  }

  function changeFontSize(delta) {
    fontSize = Math.max(50, Math.min(250, fontSize + delta));
    applyStyles();
    savePosition();
  }

  function setFontFamily(value) {
    fontFamily = value;
    applyStyles();
    savePosition();
  }

  function changeLineHeight(delta) {
    lineHeight = Math.max(1.0, Math.min(3.0, Math.round((lineHeight + delta) * 10) / 10));
    applyStyles();
    savePosition();
  }

  // CSS in alle geladenen iframes injizieren
  function applyStyles() {
    if (!view?.renderer) return;
    const contents = view.renderer.getContents();
    for (const { doc } of contents) {
      injectCSS(doc);
    }
    // Container-Hintergrund
    if (containerEl) {
      containerEl.style.backgroundColor = bgColor;
    }
  }

  function injectCSS(doc) {
    if (!doc) return;
    let styleEl = doc.getElementById("bf-reader-styles");
    if (!styleEl) {
      styleEl = doc.createElement("style");
      styleEl.id = "bf-reader-styles";
      doc.head.appendChild(styleEl);
    }
    const fontDecl = fontFamily ? `font-family: ${fontFamily} !important;` : "";
    styleEl.textContent = `
      html, body {
        color: ${fgColor} !important;
        background-color: ${bgColor} !important;
        font-size: ${fontSize}% !important;
        line-height: ${lineHeight} !important;
        ${fontDecl}
      }
      * {
        color: inherit !important;
        border-color: ${fgColor}33 !important;
      }
      a { color: ${fgColor} !important; text-decoration: underline !important; }
      img, svg, video, canvas { max-width: 100% !important; height: auto !important; }
    `;
  }

  $effect(() => {
    if (containerEl) ladeEpub(bookId);
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

      const blob = await response.blob();
      const file = new File([blob], "buch.epub", { type: "application/epub+zip" });

      if (view) {
        view.close();
        view.remove();
      }

      view = new View();
      view.style.cssText = "width: 100%; height: 100%;";
      containerEl.innerHTML = "";
      containerEl.style.backgroundColor = bgColor;
      containerEl.appendChild(view);

      await view.open(file);

      if (view.book?.toc) {
        tocItems = flattenToc(view.book.toc);
      }

      // Bei jedem Section-Load CSS injizieren
      view.addEventListener("load", (e) => {
        injectCSS(e.detail.doc);
      });

      view.addEventListener("relocate", (e) => {
        currentLocation = e.detail;
        if (e.detail.fraction != null) {
          fortschritt = Math.round(e.detail.fraction * 100);
        }
        savePosition();
      });

      await view.init({
        lastLocation: initialCfi || undefined,
      });

      // Initiale Styles anwenden
      applyStyles();
      laden = false;
    } catch (e) {
      fehler = e.message || "EPUB konnte nicht geladen werden";
      laden = false;
    }
  }

  function flattenToc(toc, depth = 0) {
    const result = [];
    for (const item of toc) {
      result.push({ ...item, depth });
      if (item.subitems?.length) {
        result.push(...flattenToc(item.subitems, depth + 1));
      }
    }
    return result;
  }

  function goToTocItem(href) {
    if (!view) return;
    view.goTo(href);
    showToc = false;
  }

  async function nextPage() {
    if (!view) return;
    await view.next();
  }

  async function prevPage() {
    if (!view) return;
    await view.prev();
  }

  function handleKeydown(event) {
    if (event.target.tagName === "INPUT" || event.target.tagName === "SELECT") return;
    if (event.key === "ArrowRight" || event.key === "PageDown") {
      event.preventDefault();
      nextPage();
    } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
      event.preventDefault();
      prevPage();
    } else if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      changeFontSize(10);
    } else if (event.key === "-") {
      event.preventDefault();
      changeFontSize(-10);
    }
  }

  let saveTimeout;
  function savePosition() {
    clearTimeout(saveTimeout);
    const params = new URLSearchParams();
    if (currentLocation?.cfi) params.set("cfi", currentLocation.cfi);
    const newUrl = `/book/${bookId}/read${params.toString() ? "?" + params.toString() : ""}`;
    history.replaceState(null, "", newUrl);

    saveTimeout = setTimeout(async () => {
      const settings = {
        cfi: currentLocation?.cfi || "",
        fontSize,
        fontFamily,
        lineHeight,
        fgColor,
        bgColor,
        maxWidthSingle,
        maxWidthDouble,
        singlePage,
      };
      const pos = `epub:${JSON.stringify(settings)}`;
      onPositionChange(pos);
      try {
        await speichereLeseposition(bookId, pos);
      } catch { /* still */ }
    }, 1500);
  }

  function downloadFile() {
    const a = document.createElement("a");
    a.href = dateiUrl(bookId);
    a.download = title || `buch-${bookId}.epub`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  onDestroy(() => {
    clearTimeout(saveTimeout);
    if (view) {
      view.close();
      view.remove();
      view = null;
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="epub-reader">
  {#if laden}
    <div class="status">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <span>EPUB wird geladen...</span>
    </div>
  {:else if fehler}
    <div class="status error">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <span>{fehler}</span>
    </div>
  {:else}
    <div class="epub-toolbar">
      <button class="tool-btn" onclick={onBack} title="Zurück">
        <i class="fa-solid fa-arrow-left"></i>
      </button>
      <span class="toolbar-title" title={title}>{title}</span>

      <div class="toolbar-sep"></div>

      <!-- Navigation -->
      <div class="toolbar-group">
        <button class="tool-btn" onclick={prevPage} title="Vorherige Seite">
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <span class="progress-info">{fortschritt}%</span>
        <button class="tool-btn" onclick={nextPage} title="Nächste Seite">
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>

      <div class="toolbar-sep"></div>

      <!-- Schriftgröße -->
      <div class="toolbar-group">
        <button class="tool-btn" onclick={() => changeFontSize(-10)} title="Kleiner" disabled={fontSize <= 50}>
          <i class="fa-solid fa-minus"></i>
        </button>
        <button class="zoom-display" onclick={() => { fontSize = 100; applyStyles(); savePosition(); }} title="Zurücksetzen">
          {fontSize}%
        </button>
        <button class="tool-btn" onclick={() => changeFontSize(10)} title="Größer" disabled={fontSize >= 250}>
          <i class="fa-solid fa-plus"></i>
        </button>
      </div>

      <div class="toolbar-sep"></div>

      <!-- Inhaltsverzeichnis -->
      <button class="tool-btn" class:active={showToc} onclick={() => { showToc = !showToc; showSettings = false; }} title="Inhaltsverzeichnis">
        <i class="fa-solid fa-list"></i>
      </button>

      <!-- Einseitig/Zweiseitig -->
      <button
        class="tool-btn"
        class:active={singlePage}
        onclick={() => { singlePage = !singlePage; savePosition(); }}
        title={singlePage ? "Zweiseitig" : "Einseitig"}
      >
        <i class="fa-solid {singlePage ? 'fa-file' : 'fa-book-open'}"></i>
      </button>

      <!-- Einstellungen -->
      <button class="tool-btn" class:active={showSettings} onclick={() => { showSettings = !showSettings; showToc = false; }} title="Leseeinstellungen">
        <i class="fa-solid fa-sliders"></i>
      </button>

      <div class="toolbar-spacer"></div>

      {#if currentLocation?.tocItem}
        <span class="chapter-info" title={currentLocation.tocItem.label}>
          {currentLocation.tocItem.label}
        </span>
      {/if}

      <button class="tool-btn" onclick={downloadFile} title="Herunterladen">
        <i class="fa-solid fa-download"></i>
      </button>
    </div>

    <!-- Fortschrittsbalken -->
    <div class="progress-bar">
      <div class="progress-fill" style="width: {fortschritt}%"></div>
    </div>
  {/if}

  <!-- Reader-Container -->
  <div
    class="reader-container"
    class:single-page={singlePage}
    style="--reader-max-width: {activeMaxWidth}px"
    bind:this={containerEl}
  ></div>

  <!-- Inhaltsverzeichnis Overlay -->
  {#if showToc && tocItems.length > 0}
    <div class="side-overlay">
      <div class="side-panel">
        <div class="panel-header">
          <span class="panel-title">Inhaltsverzeichnis</span>
          <button class="tool-btn" onclick={() => { showToc = false; }}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="toc-list">
          {#each tocItems as item}
            <button
              class="toc-item"
              style="padding-left: {0.75 + item.depth * 1}rem"
              onclick={() => goToTocItem(item.href)}
            >
              {item.label}
            </button>
          {/each}
        </div>
      </div>
      <button class="side-backdrop" onclick={() => { showToc = false; }}></button>
    </div>
  {/if}

  <!-- Einstellungen Panel (ohne Overlay) -->
  {#if showSettings}
    <div class="settings-float">
      <div class="side-panel settings-panel">
        <div class="panel-header">
          <span class="panel-title">Leseeinstellungen</span>
          <button class="tool-btn" onclick={() => { showSettings = false; }}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>

        <div class="settings-content">
          <!-- Farbthemen -->
          <div class="setting-section">
            <label class="setting-label">Farbthema</label>
            <div class="theme-grid">
              {#each farbThemen as theme, i}
                <button
                  class="theme-btn"
                  class:active={i === activeThemeIndex}
                  style="background-color: {theme.bg || bgColor}; color: {theme.fg || fgColor}; border-color: {i === activeThemeIndex ? 'var(--color-accent)' : (theme.fg || fgColor) + '33'};"
                  onclick={() => setFarbThema(theme)}
                  title={theme.name}
                >
                  <i class="fa-solid {theme.icon}"></i>
                  <span class="theme-label">{theme.name}</span>
                </button>
              {/each}
            </div>
          </div>

          <!-- Feinregler Hintergrund -->
          <div class="setting-section">
            <label class="setting-label">Hintergrund</label>
            <div class="color-row">
              <input type="color" bind:value={bgColor} oninput={() => { applyStyles(); savePosition(); }} class="color-picker" />
              <span class="color-value">{bgColor}</span>
            </div>
          </div>

          <!-- Feinregler Vordergrund -->
          <div class="setting-section">
            <label class="setting-label">Textfarbe</label>
            <div class="color-row">
              <input type="color" bind:value={fgColor} oninput={() => { applyStyles(); savePosition(); }} class="color-picker" />
              <span class="color-value">{fgColor}</span>
            </div>
          </div>

          <!-- Schriftart -->
          <div class="setting-section">
            <label class="setting-label">Schriftart</label>
            <div class="font-list">
              {#each schriften as s}
                <button
                  class="font-btn"
                  class:active={fontFamily === s.value}
                  style="font-family: {s.value || 'inherit'}"
                  onclick={() => setFontFamily(s.value)}
                >
                  {s.name}
                </button>
              {/each}
            </div>
          </div>

          <!-- Schriftgröße -->
          <div class="setting-section">
            <label class="setting-label">Schriftgröße</label>
            <div class="slider-row">
              <button class="slider-btn" onclick={() => changeFontSize(-10)} disabled={fontSize <= 50}>
                <i class="fa-solid fa-minus"></i>
              </button>
              <input
                type="range"
                min="50"
                max="250"
                step="10"
                bind:value={fontSize}
                oninput={() => { applyStyles(); savePosition(); }}
                class="range-slider"
              />
              <button class="slider-btn" onclick={() => changeFontSize(10)} disabled={fontSize >= 250}>
                <i class="fa-solid fa-plus"></i>
              </button>
              <span class="slider-value">{fontSize}%</span>
            </div>
          </div>

          <!-- Zeilenabstand -->
          <div class="setting-section">
            <label class="setting-label">Zeilenabstand</label>
            <div class="slider-row">
              <button class="slider-btn" onclick={() => changeLineHeight(-0.1)} disabled={lineHeight <= 1.0}>
                <i class="fa-solid fa-minus"></i>
              </button>
              <input
                type="range"
                min="1.0"
                max="3.0"
                step="0.1"
                bind:value={lineHeight}
                oninput={() => { applyStyles(); savePosition(); }}
                class="range-slider"
              />
              <button class="slider-btn" onclick={() => changeLineHeight(0.1)} disabled={lineHeight >= 3.0}>
                <i class="fa-solid fa-plus"></i>
              </button>
              <span class="slider-value">{lineHeight.toFixed(1)}</span>
            </div>
          </div>

          <!-- Layout -->
          <div class="setting-section">
            <label class="setting-label">Layout</label>
            <div class="layout-row">
              <button
                class="layout-btn"
                class:active={!singlePage}
                onclick={() => { singlePage = false; savePosition(); }}
              >
                <i class="fa-solid fa-book-open"></i> Zweiseitig
              </button>
              <button
                class="layout-btn"
                class:active={singlePage}
                onclick={() => { singlePage = true; savePosition(); }}
              >
                <i class="fa-solid fa-file"></i> Einseitig
              </button>
            </div>
          </div>

          <!-- Breite Einseitig -->
          <div class="setting-section">
            <label class="setting-label">Breite einseitig</label>
            <div class="slider-row">
              <button class="slider-btn" onclick={() => { maxWidthSingle = Math.max(300, maxWidthSingle - 50); savePosition(); }} disabled={maxWidthSingle <= 300}>
                <i class="fa-solid fa-minus"></i>
              </button>
              <input
                type="range"
                min="300"
                max="1200"
                step="50"
                bind:value={maxWidthSingle}
                oninput={() => { savePosition(); }}
                class="range-slider"
              />
              <button class="slider-btn" onclick={() => { maxWidthSingle = Math.min(1200, maxWidthSingle + 50); savePosition(); }} disabled={maxWidthSingle >= 1200}>
                <i class="fa-solid fa-plus"></i>
              </button>
              <span class="slider-value">{maxWidthSingle}px</span>
            </div>
          </div>

          <!-- Breite Zweiseitig -->
          <div class="setting-section">
            <label class="setting-label">Breite zweiseitig</label>
            <div class="slider-row">
              <button class="slider-btn" onclick={() => { maxWidthDouble = Math.max(600, maxWidthDouble - 50); savePosition(); }} disabled={maxWidthDouble <= 600}>
                <i class="fa-solid fa-minus"></i>
              </button>
              <input
                type="range"
                min="600"
                max="2400"
                step="50"
                bind:value={maxWidthDouble}
                oninput={() => { savePosition(); }}
                class="range-slider"
              />
              <button class="slider-btn" onclick={() => { maxWidthDouble = Math.min(2400, maxWidthDouble + 50); savePosition(); }} disabled={maxWidthDouble >= 2400}>
                <i class="fa-solid fa-plus"></i>
              </button>
              <span class="slider-value">{maxWidthDouble}px</span>
            </div>
          </div>

          <!-- Vorschau -->
          <div class="setting-section">
            <label class="setting-label">Vorschau</label>
            <div
              class="preview-box"
              style="background-color: {bgColor}; color: {fgColor}; font-size: {fontSize * 0.14}px; line-height: {lineHeight}; font-family: {fontFamily || 'inherit'};"
            >
              Die Sonne ging unter und tauchte die Stadt in ein warmes, goldenes Licht.
              Sie blickte aus dem Fenster und dachte an die vergangenen Jahre.
            </div>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  /* Settings Float (Glasmorphism) */
  .settings-float {
    position: absolute;
    top: 38px;
    right: 0;
    bottom: 0;
    z-index: 30;
    pointer-events: none;
  }

  .settings-float .side-panel {
    pointer-events: auto;
    margin-left: auto;
    background: rgba(20, 30, 48, 0.88);
    backdrop-filter: blur(24px) saturate(1.3);
    -webkit-backdrop-filter: blur(24px) saturate(1.3);
    border-left: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: -8px 0 32px rgba(0, 0, 0, 0.3);
  }

  :global(:root:not(.dark)) .settings-float .side-panel {
    background: rgba(255, 255, 255, 0.88);
    border-left: 1px solid rgba(0, 0, 0, 0.08);
    box-shadow: -8px 0 32px rgba(0, 0, 0, 0.12);
  }

  .settings-float .panel-header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: transparent;
  }

  :global(:root:not(.dark)) .settings-float .panel-header {
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  }

  .epub-reader {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    position: relative;
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
  .epub-toolbar {
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

  .progress-info {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    min-width: 2.5rem;
    text-align: center;
  }

  .chapter-info {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
    margin-right: 0.5rem;
  }

  /* Fortschrittsbalken */
  .progress-bar {
    height: 2px;
    background-color: var(--color-bg-tertiary);
    flex-shrink: 0;
  }

  .progress-fill {
    height: 100%;
    background-color: var(--color-accent);
    transition: width 0.3s ease;
  }

  /* Reader-Container */
  .reader-container {
    flex: 1;
    overflow: hidden;
    background-color: #fff;
    min-height: 0;
    transition: background-color 0.2s;
    width: 100%;
    max-width: var(--reader-max-width);
    margin: 0 auto;
  }

  /* Side Overlays (TOC + Settings) */
  .side-overlay {
    position: absolute;
    inset: 38px 0 0 0;
    z-index: 30;
    display: flex;
  }

  .side-overlay.from-right {
    flex-direction: row-reverse;
  }

  .side-panel {
    width: min(340px, 85%);
    background-color: var(--color-bg-secondary);
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    box-shadow: 4px 0 12px rgba(0, 0, 0, 0.15);
    max-height: 100%;
  }

  .from-right .side-panel {
    border-right: none;
    border-left: 1px solid var(--color-border);
    box-shadow: -4px 0 12px rgba(0, 0, 0, 0.15);
  }

  .side-backdrop {
    flex: 1;
    background: rgba(0, 0, 0, 0.3);
    border: none;
    cursor: pointer;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
  }

  .panel-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  /* TOC */
  .toc-list {
    flex: 1;
    overflow-y: auto;
  }

  .toc-item {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.5rem 0.75rem;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    border-bottom: 1px solid var(--color-border);
  }

  .toc-item:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  /* Settings */
  .settings-panel {
    width: min(320px, 85%);
  }

  .settings-content {
    flex: 1;
    overflow-y: auto;
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .setting-section {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .setting-label {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* Farbthemen */
  .theme-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.375rem;
  }

  .theme-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
    padding: 0.5rem 0.25rem;
    border: 2px solid;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    transition: transform 0.1s;
  }

  .theme-btn:hover {
    transform: scale(1.05);
  }

  .theme-btn.active {
    border-width: 2px;
  }

  .theme-label {
    font-size: 0.5625rem;
    font-weight: 500;
  }

  /* Feinregler Farben */
  .color-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .color-picker {
    width: 32px;
    height: 24px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    background: none;
  }

  .color-picker::-webkit-color-swatch-wrapper {
    padding: 2px;
  }

  .color-picker::-webkit-color-swatch {
    border: none;
    border-radius: 2px;
  }

  .color-value {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }

  /* Schriftart */
  .font-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .font-btn {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.375rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    cursor: pointer;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    transition: background-color 0.1s;
  }

  .font-btn:hover {
    background-color: var(--color-bg-tertiary);
  }

  .font-btn.active {
    background-color: var(--color-accent-light);
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  /* Slider */
  .slider-row {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .slider-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 0.625rem;
    flex-shrink: 0;
  }

  .slider-btn:hover:not(:disabled) {
    background-color: var(--color-bg-tertiary);
  }

  .slider-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .range-slider {
    flex: 1;
    height: 4px;
    accent-color: var(--color-accent);
    cursor: pointer;
  }

  .slider-value {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    min-width: 2.5rem;
    text-align: right;
    flex-shrink: 0;
  }

  /* Layout-Buttons */
  .layout-row {
    display: flex;
    gap: 0.375rem;
  }

  .layout-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.375rem;
    padding: 0.375rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    cursor: pointer;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .layout-btn:hover {
    background-color: var(--color-bg-tertiary);
  }

  .layout-btn.active {
    background-color: var(--color-accent-light);
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  /* Vorschau */
  .preview-box {
    padding: 0.75rem;
    border-radius: 6px;
    border: 1px solid var(--color-border);
    transition: all 0.2s;
  }
</style>
