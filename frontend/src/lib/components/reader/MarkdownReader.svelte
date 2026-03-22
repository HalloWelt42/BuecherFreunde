<script>
  import { dateiUrl } from "../../api/books.js";
  import { getToken } from "../../api/client.js";
  import { speichereLeseposition } from "../../api/user-data.js";
  import { ui } from "../../stores/ui.svelte.js";
  import { untrack } from "svelte";
  import SvelteMarkdown from "@humanspeak/svelte-markdown";
  import { markedMermaid, MermaidRenderer } from "@humanspeak/svelte-markdown/extensions";
  import AlertBlock from "./AlertBlock.svelte";
  import { readerFarbThemen, readerSchriften } from "../../constants/themes.js";
  import TextSelectionMenu from "./TextSelectionMenu.svelte";
  import LabelPicker from "./LabelPicker.svelte";
  import ReaderLabels from "./ReaderLabels.svelte";

  let {
    bookId,
    title = "",
    format = "txt",
    initialPapier = "",
    initialFontSize = 0,
    initialFontFamily = "",
    initialScrollPct = 0,
    initialBreite = -1,
    initialFgColor = "",
    initialBgColor = "",
    onBack = () => {},
    onPositionChange = () => {},
  } = $props();

  let content = $state("");
  let laden = $state(true);
  let fehler = $state(null);
  let fontSize = $state(untrack(() => initialFontSize > 0 ? initialFontSize : 100));
  let scrollContainer = $state(null);

  // Schriftarten und Farbthemen (zentral definiert)
  const schriften = readerSchriften;
  let fontFamily = $state(untrack(() => initialFontFamily || ""));
  const farbThemen = readerFarbThemen;
  let fgColor = $state(untrack(() => initialFgColor || "#1a1a1a"));
  let bgColor = $state(untrack(() => initialBgColor || "#ffffff"));
  let activeThemeIndex = $derived.by(() => {
    const idx = farbThemen.findIndex(t => t.fg === fgColor && t.bg === bgColor);
    return idx >= 0 ? idx : -1;
  });
  let istDunkel = $derived(bgColor === "#1e1e1e" || bgColor === "#0a0a0a" || bgColor === "#3d3526");

  function setzeThema(theme) {
    fgColor = theme.fg;
    bgColor = theme.bg;
    triggerSave();
  }

  // Einstellungspanel
  let settingsOffen = $state(false);

  // Markdown oder Plaintext?
  let istMarkdown = $derived(format === "md");

  // Erweiterte Alert-Typen (Obsidian-kompatibel) auf unsere 5 Grundtypen gemappt
  const ALERT_ALIASES = {
    note: "note", info: "note", abstract: "note", summary: "note", tldr: "note",
    tip: "tip", hint: "tip", success: "tip", check: "tip", done: "tip",
    important: "important", faq: "important", question: "important",
    warning: "warning", attention: "warning", todo: "warning",
    caution: "caution", danger: "caution", error: "caution", failure: "caution",
    bug: "caution", example: "note", quote: "note", cite: "note",
  };

  function customAlert() {
    return {
      extensions: [{
        name: "alert",
        level: "block",
        start(src) { return src.match(/>\s*\[!/)?.index; },
        tokenizer(src) {
          // Format 1: > [!type] Text auf gleicher Zeile (Obsidian)
          // Format 2: > [!type]\n> Text auf Folgezeilen (GitHub)
          const match = src.match(/^>\s*\[!(\w+)\][ \t]*(.*?)(?:\n((?:>\s?[^\n]*(?:\n|$))*))?(?:\n|$)/);
          if (!match) return;
          const raw = match[1].toLowerCase();
          const alertType = ALERT_ALIASES[raw];
          if (!alertType) return;
          // Titel von der ersten Zeile
          const titleText = (match[2] || "").trim();
          // Folgezeilen (> prefixed)
          const bodyLines = (match[3] || "")
            .split("\n")
            .map((line) => line.replace(/^>\s?/, ""))
            .join("\n")
            .trim();
          const text = [titleText, bodyLines].filter(Boolean).join("\n");
          return { type: "alert", raw: match[0], text, alertType };
        },
      }],
    };
  }

  // Markdown-Erweiterungen und Renderer
  const mdExtensions = [markedMermaid(), customAlert()];
  const mdRenderers = { mermaid: MermaidRenderer, alert: AlertBlock };

  // Breiten-Modi
  const breitenModi = [
    { id: "schmal", label: "Schmal", max: "600px" },
    { id: "mittel", label: "Mittel", max: "800px" },
    { id: "breit", label: "Breit", max: "1100px" },
    { id: "voll", label: "Voll", max: "none" },
  ];
  let breiteIdx = $state(untrack(() => initialBreite >= 0 && initialBreite < breitenModi.length ? initialBreite : 1));
  let maxBreite = $derived(breitenModi[breiteIdx].max);

  function toggleBreite() {
    breiteIdx = (breiteIdx + 1) % breitenModi.length;
    triggerSave();
  }

  // Geschaetzte Seiten (~2000 Zeichen pro Seite)
  const ZEICHEN_PRO_SEITE = 2000;
  let geschaetzteSeiten = $derived(Math.max(1, Math.ceil(content.length / ZEICHEN_PRO_SEITE)));
  let aktuelleSeite = $state(1);
  let fortschritt = $state(0);

  // Papier-Modus entfernt, jetzt Farbthemen

  $effect(() => {
    ladeText(bookId);
  });

  // Fullscreen-State synchron halten (z.B. wenn Nutzer per Geste Vollbild verlaesst)
  $effect(() => {
    function onFsChange() {
      const isFs = !!(document.fullscreenElement || document.webkitFullscreenElement);
      ui.readerFullscreen = isFs;
    }
    document.addEventListener("fullscreenchange", onFsChange);
    document.addEventListener("webkitfullscreenchange", onFsChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFsChange);
      document.removeEventListener("webkitfullscreenchange", onFsChange);
    };
  });

  // Syntax-Highlighting + Copy-Buttons nach Markdown-Rendering anwenden
  $effect(() => {
    if (!laden && istMarkdown && content && scrollContainer) {
      // Kurz warten bis SvelteMarkdown gerendert hat
      requestAnimationFrame(() => {
        highlightCodeBlocks();
        addCopyButtons();
      });
    }
  });

  async function highlightCodeBlocks() {
    try {
      const hljs = await import("highlight.js/lib/core");
      const hljsLib = hljs.default;

      // Sprachen on-demand laden
      const languages = {
        javascript: () => import("highlight.js/lib/languages/javascript"),
        typescript: () => import("highlight.js/lib/languages/typescript"),
        python: () => import("highlight.js/lib/languages/python"),
        bash: () => import("highlight.js/lib/languages/bash"),
        shell: () => import("highlight.js/lib/languages/shell"),
        json: () => import("highlight.js/lib/languages/json"),
        xml: () => import("highlight.js/lib/languages/xml"),
        css: () => import("highlight.js/lib/languages/css"),
        sql: () => import("highlight.js/lib/languages/sql"),
        java: () => import("highlight.js/lib/languages/java"),
        c: () => import("highlight.js/lib/languages/c"),
        cpp: () => import("highlight.js/lib/languages/cpp"),
        csharp: () => import("highlight.js/lib/languages/csharp"),
        go: () => import("highlight.js/lib/languages/go"),
        rust: () => import("highlight.js/lib/languages/rust"),
        ruby: () => import("highlight.js/lib/languages/ruby"),
        php: () => import("highlight.js/lib/languages/php"),
        yaml: () => import("highlight.js/lib/languages/yaml"),
        markdown: () => import("highlight.js/lib/languages/markdown"),
        dockerfile: () => import("highlight.js/lib/languages/dockerfile"),
        ini: () => import("highlight.js/lib/languages/ini"),
        diff: () => import("highlight.js/lib/languages/diff"),
        plaintext: () => import("highlight.js/lib/languages/plaintext"),
      };

      // Alle Code-Bloecke finden (nur die ohne Mermaid)
      const codeBlocks = scrollContainer.querySelectorAll("pre code");
      if (codeBlocks.length === 0) return;

      // Benoetigte Sprachen registrieren
      const needed = new Set();
      for (const block of codeBlocks) {
        const cls = [...block.classList].find(c => c.startsWith("language-"));
        if (cls) {
          const lang = cls.replace("language-", "");
          const aliases = { js: "javascript", ts: "typescript", py: "python", sh: "bash", yml: "yaml", html: "xml" };
          needed.add(aliases[lang] || lang);
        }
      }

      // Sprachen registrieren
      for (const lang of needed) {
        if (languages[lang] && !hljsLib.getLanguage(lang)) {
          try {
            const mod = await languages[lang]();
            hljsLib.registerLanguage(lang, mod.default);
          } catch { /* Sprache nicht verfuegbar */ }
        }
      }

      // Wenn keine spezifischen Sprachen, gaengige laden fuer Auto-Detect
      if (needed.size === 0) {
        for (const lang of ["javascript", "python", "bash", "json", "xml", "css", "sql"]) {
          if (!hljsLib.getLanguage(lang)) {
            try {
              const mod = await languages[lang]();
              hljsLib.registerLanguage(lang, mod.default);
            } catch { /* */ }
          }
        }
      }

      // Highlighting anwenden
      for (const block of codeBlocks) {
        if (!block.dataset.highlighted) {
          hljsLib.highlightElement(block);
          block.dataset.highlighted = "true";
        }
      }
    } catch (e) {
      console.warn("Syntax-Highlighting fehlgeschlagen:", e);
    }
  }

  function addCopyButtons() {
    if (!scrollContainer) return;
    const preBlocks = scrollContainer.querySelectorAll("pre");
    for (const pre of preBlocks) {
      if (pre.querySelector(".code-copy-btn")) continue;
      // Wrapper fuer position:relative
      pre.style.position = "relative";
      const btn = document.createElement("button");
      btn.className = "code-copy-btn";
      btn.innerHTML = '<i class="fa-regular fa-copy"></i>';
      btn.title = "Code kopieren";
      btn.addEventListener("click", async () => {
        const code = pre.querySelector("code");
        const text = code ? code.textContent : pre.textContent;
        try {
          await navigator.clipboard.writeText(text);
          btn.innerHTML = '<i class="fa-solid fa-check"></i>';
          btn.classList.add("copied");
          setTimeout(() => {
            btn.innerHTML = '<i class="fa-regular fa-copy"></i>';
            btn.classList.remove("copied");
          }, 2000);
        } catch { /* Clipboard nicht verfuegbar */ }
      });
      pre.appendChild(btn);
    }
  }

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

  let saveTimeout;
  function triggerSave() {
    clearTimeout(saveTimeout);
    const params = new URLSearchParams();
    if (fortschritt > 0) params.set("pos", String(fortschritt));
    if (fontSize !== 100) params.set("font", String(fontSize));
    const newUrl = `/book/${bookId}/read${params.toString() ? "?" + params.toString() : ""}`;
    history.replaceState(null, "", newUrl);

    saveTimeout = setTimeout(async () => {
      const settings = {
        scrollPct: fortschritt,
        fontSize,
        fontFamily,
        breite: breiteIdx,
        fgColor,
        bgColor,
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
    a.download = title || `buch-${bookId}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function handleKeydown(event) {
    if (event.key === "Escape" && ui.readerFullscreen) {
      event.preventDefault();
      ui.readerFullscreen = false;
    }
  }

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

<svelte:window onkeydown={handleKeydown} />

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

      <div class="toolbar-group">
        <span class="page-info">~{aktuelleSeite} / {geschaetzteSeiten}</span>
        <span class="progress-info">{fortschritt}%</span>
      </div>

      <div class="toolbar-sep"></div>

      <span class="format-badge">{istMarkdown ? "MD" : "TXT"}</span>

      <div class="toolbar-sep"></div>

      <!-- Schriftgroesse -->
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

      <!-- Breite -->
      <button
        class="tool-btn breite-btn"
        onclick={toggleBreite}
        title="Textbreite: {breitenModi[breiteIdx].label}"
      >
        <i class="fa-solid fa-left-right"></i>
        <span class="breite-label">{breitenModi[breiteIdx].label}</span>
      </button>

      <div class="toolbar-sep"></div>

      <!-- Einstellungen (Schrift, Theme) -->
      <button
        class="tool-btn"
        class:active={settingsOffen}
        onclick={() => settingsOffen = !settingsOffen}
        title="Darstellung"
      >
        <i class="fa-solid fa-palette"></i>
      </button>

      <div class="toolbar-sep"></div>

      <button class="tool-btn" onclick={() => {}} title="Text auswählen zum Markieren, Kopieren oder als Notiz speichern" style="cursor: help;">
        <i class="fa-solid fa-highlighter"></i>
      </button>

      <LabelPicker
        {bookId}
        positionLabel={"~S." + aktuelleSeite}
        positionPercent={fortschritt}
      />

      <ReaderLabels
        {bookId}
        onNavigate={(label) => {
          if (label.position_percent > 0 && scrollContainer) {
            const scrollMax = scrollContainer.scrollHeight - scrollContainer.clientHeight;
            scrollContainer.scrollTop = (label.position_percent / 100) * scrollMax;
          }
        }}
      />

      <div class="toolbar-spacer"></div>

      <button class="tool-btn" class:active={ui.readerFullscreen} onclick={() => ui.toggleReaderFullscreen()} title="{ui.readerFullscreen ? 'Vollbild verlassen' : 'Vollbild'}">
        <i class="fa-solid {ui.readerFullscreen ? 'fa-compress' : 'fa-expand'}"></i>
      </button>
      <button class="tool-btn" onclick={downloadFile} title="Herunterladen">
        <i class="fa-solid fa-download"></i>
      </button>
    </div>

    {#if settingsOffen}
      <div class="settings-panel">
        <div class="settings-row">
          <span class="settings-label">Schriftart</span>
          <div class="settings-options">
            {#each schriften as s}
              <button
                class="option-btn"
                class:active={fontFamily === s.value}
                onclick={() => { fontFamily = s.value; triggerSave(); }}
                style="font-family: {s.value || 'inherit'}"
              >{s.name}</button>
            {/each}
          </div>
        </div>
        <div class="settings-row">
          <span class="settings-label">Farbthema</span>
          <div class="settings-options">
            {#each farbThemen as theme, i}
              <button
                class="theme-btn"
                class:active={activeThemeIndex === i}
                onclick={() => setzeThema(theme)}
                title={theme.name}
                style="background-color: {theme.bg}; color: {theme.fg}; border-color: {activeThemeIndex === i ? 'var(--color-accent)' : theme.bg === '#ffffff' ? '#ccc' : theme.bg}"
              >
                <i class="fa-solid {theme.icon}"></i>
              </button>
            {/each}
          </div>
        </div>
      </div>
    {/if}

    <div
      class="text-content"
      class:ist-dunkel={istDunkel}
      bind:this={scrollContainer}
      onscroll={handleScroll}
      style="background-color: {bgColor}; color: {fgColor};"
    >
      {#if istMarkdown}
        <div class="markdown-body" style="font-size: {fontSize}%; max-width: {maxBreite}; font-family: {fontFamily || 'inherit'}">
          <SvelteMarkdown source={content} extensions={mdExtensions} renderers={mdRenderers} />
        </div>
      {:else}
        <pre class="text-pre" style="font-size: {fontSize}%; max-width: {maxBreite}; font-family: {fontFamily || 'var(--font-sans)'}">{content}</pre>
      {/if}
    </div>

    <TextSelectionMenu
      {bookId}
      positionLabel={"~S." + aktuelleSeite}
      onHighlight={(text) => {
        const sel = window.getSelection();
        if (sel?.rangeCount > 0) {
          try {
            const range = sel.getRangeAt(0);
            const mark = document.createElement("mark");
            mark.className = "user-highlight";
            range.surroundContents(mark);
          } catch { /* Verschachtelte Ranges */ }
        }
      }}
    />
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
    overflow-x: auto;
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

  .toolbar-spacer { flex: 1; }

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
    flex-shrink: 0;
  }

  .format-badge {
    font-size: 0.625rem;
    font-weight: 700;
    font-family: var(--font-mono, monospace);
    color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 15%, transparent);
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
    letter-spacing: 0.05em;
    flex-shrink: 0;
  }

  .tool-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 0.75rem;
    transition: background-color 0.1s;
    flex-shrink: 0;
  }

  .tool-btn:hover:not(:disabled) {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .tool-btn:disabled { opacity: 0.3; cursor: default; }

  .tool-btn.active {
    background-color: color-mix(in srgb, var(--color-accent) 15%, transparent);
    color: var(--color-accent);
  }

  .breite-btn {
    gap: 0.25rem;
    padding: 0 0.375rem;
  }

  .breite-label {
    font-size: 0.625rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .page-info, .progress-info {
    font-size: 0.75rem;
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .progress-info { min-width: 2rem; text-align: center; }

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

  .zoom-display:hover { background-color: var(--color-bg-tertiary); }

  /* Settings-Panel */
  .settings-panel {
    display: flex;
    gap: 1.5rem;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    flex-shrink: 0;
    flex-wrap: wrap;
    align-items: center;
  }

  .settings-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .settings-label {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .settings-options {
    display: flex;
    gap: 0.25rem;
  }

  .option-btn {
    padding: 0.2rem 0.5rem;
    font-size: 0.6875rem;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: all 0.1s;
  }

  .option-btn:hover {
    background-color: var(--color-bg-tertiary);
  }

  .option-btn.active {
    background-color: color-mix(in srgb, var(--color-accent) 15%, transparent);
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  .theme-btn {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.6875rem;
    transition: transform 0.1s;
  }

  .theme-btn:hover { transform: scale(1.15); }
  .theme-btn.active { transform: scale(1.15); box-shadow: 0 0 0 2px var(--color-accent); }

  /* Text-Inhalt */
  .text-content {
    flex: 1;
    overflow: auto;
    padding: 2rem;
  }

  /* Plaintext */
  .text-pre {
    line-height: 1.7;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: inherit;
    margin: 0 auto;
  }

  /* Markdown-Body */
  .markdown-body {
    margin: 0 auto;
    color: inherit;
    line-height: 1.7;
  }

  /* Ueberschriften */
  .markdown-body :global(h1) {
    font-size: 1.75em; font-weight: 700; margin: 1.5em 0 0.75em;
    padding-bottom: 0.3em; border-bottom: 1px solid var(--color-border);
  }
  .markdown-body :global(h2) {
    font-size: 1.4em; font-weight: 700; margin: 1.25em 0 0.5em;
    padding-bottom: 0.25em; border-bottom: 1px solid var(--color-border);
  }
  .markdown-body :global(h3) { font-size: 1.2em; font-weight: 600; margin: 1em 0 0.5em; }
  .markdown-body :global(h4),
  .markdown-body :global(h5),
  .markdown-body :global(h6) { font-size: 1em; font-weight: 600; margin: 1em 0 0.5em; }

  .markdown-body :global(p) { margin: 0.75em 0; }
  .markdown-body :global(strong) { font-weight: 700; }
  .markdown-body :global(a) { color: var(--color-accent); text-decoration: none; }
  .markdown-body :global(a:hover) { text-decoration: underline; }

  /* Listen */
  .markdown-body :global(ul), .markdown-body :global(ol) { padding-left: 1.5em; margin: 0.5em 0; }
  .markdown-body :global(li) { margin: 0.25em 0; }

  /* Blockquotes */
  .markdown-body :global(blockquote) {
    margin: 0.75em 0; padding: 0.5em 1em;
    border-left: 4px solid var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 5%, transparent);
    opacity: 0.85;
  }
  .markdown-body :global(blockquote p) { margin: 0.25em 0; }

  /* Inline-Code */
  .markdown-body :global(code) {
    font-family: "JetBrains Mono", var(--font-mono, monospace);
    font-weight: 700;
    font-size: 0.875em;
    background: color-mix(in srgb, var(--color-text-primary) 8%, transparent);
    padding: 0.15em 0.4em; border-radius: 4px;
  }

  /* Code-Bloecke - Dracula Theme */
  .markdown-body :global(pre) {
    margin: 1em 0; padding: 1em; border-radius: 6px;
    background: #282a36;
    border: 1px solid #44475a; overflow-x: auto;
    position: relative;
  }

  .markdown-body :global(pre code) {
    background: none; padding: 0; border-radius: 0;
    font-family: "JetBrains Mono", var(--font-mono, monospace);
    font-weight: 700;
    font-size: 0.8125em; line-height: 1.6; display: block;
    white-space: pre; overflow-x: auto;
    color: #f8f8f2;
  }

  /* Copy-Button */
  .markdown-body :global(.code-copy-btn) {
    position: sticky;
    float: right;
    top: 0.5em;
    right: 0;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.1);
    color: #6272a4;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    opacity: 0;
    transition: opacity 0.15s, background 0.15s, color 0.15s;
    z-index: 2;
    margin-top: -0.5em;
    margin-right: -0.5em;
  }

  .markdown-body :global(pre:hover .code-copy-btn) {
    opacity: 1;
  }

  .markdown-body :global(.code-copy-btn:hover) {
    background: rgba(255, 255, 255, 0.2);
    color: #f8f8f2;
  }

  .markdown-body :global(.code-copy-btn.copied) {
    color: #50fa7b;
    opacity: 1;
  }

  /* Tabellen */
  .markdown-body :global(table) { width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 0.875em; }
  .markdown-body :global(th), .markdown-body :global(td) { padding: 0.5em 0.75em; border: 1px solid var(--color-border); text-align: left; }
  .markdown-body :global(th) { background: var(--color-bg-secondary); font-weight: 600; }
  .markdown-body :global(tr:nth-child(even)) { background: color-mix(in srgb, var(--color-bg-secondary) 50%, transparent); }

  .markdown-body :global(hr) { margin: 1.5em 0; border: none; border-top: 1px solid var(--color-border); }
  .markdown-body :global(img) { max-width: 100%; border-radius: 6px; margin: 0.5em 0; }
  .markdown-body :global(input[type="checkbox"]) { margin-right: 0.375em; accent-color: var(--color-accent); }

  /* Mermaid-Diagramme */
  .markdown-body :global(.mermaid-diagram) {
    margin: 1em 0; padding: 1em; border-radius: 8px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    overflow-x: auto; text-align: center;
  }
  .markdown-body :global(.mermaid-diagram svg) { max-width: 100%; height: auto; }
  .markdown-body :global(.mermaid-loading) {
    padding: 1em; text-align: center;
    color: var(--color-text-muted); font-size: 0.875em;
  }
  .markdown-body :global(.mermaid-error) {
    padding: 0.75em 1em; border-radius: 6px; margin: 1em 0;
    background: color-mix(in srgb, var(--color-error) 10%, transparent);
    border: 1px solid var(--color-error);
    color: var(--color-error); font-size: 0.8125em;
  }

  /* highlight.js - Dracula Theme (einheitlich fuer alle Modi) */
  .markdown-body :global(.hljs-keyword) { color: #ff79c6; }
  .markdown-body :global(.hljs-string) { color: #f1fa8c; }
  .markdown-body :global(.hljs-number) { color: #bd93f9; }
  .markdown-body :global(.hljs-comment) { color: #6272a4; font-style: italic; }
  .markdown-body :global(.hljs-function),
  .markdown-body :global(.hljs-title) { color: #50fa7b; }
  .markdown-body :global(.hljs-built_in) { color: #8be9fd; font-style: italic; }
  .markdown-body :global(.hljs-literal) { color: #bd93f9; }
  .markdown-body :global(.hljs-type) { color: #8be9fd; }
  .markdown-body :global(.hljs-params) { color: #ffb86c; }
  .markdown-body :global(.hljs-meta),
  .markdown-body :global(.hljs-attr) { color: #50fa7b; }
  .markdown-body :global(.hljs-variable) { color: #f8f8f2; }
  .markdown-body :global(.hljs-selector-tag) { color: #ff79c6; }
  .markdown-body :global(.hljs-selector-class) { color: #50fa7b; }
  .markdown-body :global(.hljs-selector-id) { color: #8be9fd; }
  .markdown-body :global(.hljs-tag) { color: #ff79c6; }
  .markdown-body :global(.hljs-name) { color: #ff79c6; }
  .markdown-body :global(.hljs-attribute) { color: #50fa7b; }
  .markdown-body :global(.hljs-regexp) { color: #f1fa8c; }
  .markdown-body :global(.hljs-symbol) { color: #ff79c6; }
  .markdown-body :global(.hljs-addition) { color: #50fa7b; background-color: rgba(80, 250, 123, 0.1); }
  .markdown-body :global(.hljs-deletion) { color: #ff5555; background-color: rgba(255, 85, 85, 0.1); }
  .markdown-body :global(.hljs-doctag) { color: #8be9fd; }
  .markdown-body :global(.hljs-section) { color: #bd93f9; }
  .markdown-body :global(.hljs-property) { color: #66d9ef; }

  /* User-Highlights */
  :global(.user-highlight) { background-color: #ffe066; color: #1a1a1a; border-radius: 2px; padding: 0 1px; }
  :global(:root.dark .user-highlight) { background-color: #b8860b; color: #fff; }
</style>
