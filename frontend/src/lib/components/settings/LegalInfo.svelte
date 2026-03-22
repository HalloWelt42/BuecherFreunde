<script>
  import SvelteMarkdown from "@humanspeak/svelte-markdown";

  let activeSection = $state("lizenz");
  let markdownInhalte = $state({});
  let ladeFehler = $state({});

  const sections = [
    { id: "lizenz", label: "Lizenz", icon: "fa-scale-balanced", datei: "/legal/de/lizenz.md" },
    { id: "agb", label: "AGB", icon: "fa-file-contract", datei: "/legal/de/agb.md" },
    { id: "drittanbieter", label: "Drittanbieter", icon: "fa-cubes", datei: null },
    { id: "datenschutz", label: "Datenschutz", icon: "fa-shield-halved", datei: "/legal/de/datenschutz.md" },
    { id: "haftung", label: "Haftungsausschluss", icon: "fa-triangle-exclamation", datei: "/legal/de/haftung.md" },
    { id: "info", label: "Info", icon: "fa-circle-info", datei: "/legal/de/info.md" },
  ];

  const backendAbhaengigkeiten = [
    { name: "FastAPI", lizenz: "MIT", url: "https://github.com/tiangolo/fastapi", zweck: "Web-Framework (REST-API)" },
    { name: "Uvicorn", lizenz: "BSD-3-Clause", url: "https://github.com/encode/uvicorn", zweck: "ASGI-Server" },
    { name: "PyMuPDF", lizenz: "AGPL-3.0", url: "https://github.com/pymupdf/PyMuPDF", zweck: "PDF-Verarbeitung (Text, Cover, Metadaten)" },
    { name: "EbookLib", lizenz: "AGPL-3.0", url: "https://github.com/aerkalov/ebooklib", zweck: "EPUB-Verarbeitung" },
    { name: "mobi", lizenz: "GPL-3.0", url: "https://github.com/iscc/mobi", zweck: "MOBI-Verarbeitung" },
    { name: "Pillow", lizenz: "MIT-CMU", url: "https://github.com/python-pillow/Pillow", zweck: "Bildverarbeitung (Cover)" },
    { name: "httpx", lizenz: "BSD-3-Clause", url: "https://github.com/encode/httpx", zweck: "HTTP-Client (Metadaten-APIs, Gutenberg)" },
    { name: "aiosqlite", lizenz: "MIT", url: "https://github.com/omnilib/aiosqlite", zweck: "Async SQLite-Zugriff" },
    { name: "openai", lizenz: "Apache-2.0", url: "https://github.com/openai/openai-python", zweck: "LM Studio API-Client" },
    { name: "Pydantic Settings", lizenz: "MIT", url: "https://github.com/pydantic/pydantic-settings", zweck: "Konfigurationsverwaltung" },
    { name: "BeautifulSoup4", lizenz: "MIT", url: "https://www.crummy.com/software/BeautifulSoup/", zweck: "HTML-Parsing (Metadaten)" },
    { name: "isbnlib", lizenz: "LGPL-3.0", url: "https://github.com/xlcnd/isbnlib", zweck: "ISBN-Validierung und -Suche" },
    { name: "Wikipedia-API", lizenz: "MIT", url: "https://github.com/martin-majlis/Wikipedia-API", zweck: "Wikipedia/Wikidata-Zugriff" },
    { name: "python-multipart", lizenz: "Apache-2.0", url: "https://github.com/andrew-d/python-multipart", zweck: "Datei-Upload-Verarbeitung" },
  ];

  const frontendAbhaengigkeiten = [
    { name: "Svelte 5", lizenz: "MIT", url: "https://github.com/sveltejs/svelte", zweck: "UI-Framework" },
    { name: "Vite", lizenz: "MIT", url: "https://github.com/vitejs/vite", zweck: "Build-Tool und Dev-Server" },
    { name: "Tailwind CSS 4", lizenz: "MIT", url: "https://github.com/tailwindcss/tailwindcss", zweck: "CSS-Framework" },
    { name: "pdfjs-dist", lizenz: "Apache-2.0", url: "https://github.com/nicolo-ribaudo/pdfjs-dist", zweck: "PDF-Rendering im Browser" },
    { name: "foliate-js", lizenz: "MIT", url: "https://github.com/nicolo-ribaudo/foliate-js", zweck: "EPUB/MOBI-Reader" },
    { name: "svelte-markdown", lizenz: "MIT", url: "https://github.com/humanspeak/svelte-markdown", zweck: "Markdown-Rendering" },
    { name: "highlight.js", lizenz: "BSD-3-Clause", url: "https://github.com/highlightjs/highlight.js", zweck: "Syntax-Highlighting in Codeblöcken" },
    { name: "Mermaid", lizenz: "MIT", url: "https://github.com/mermaid-js/mermaid", zweck: "Diagramme in Markdown" },
    { name: "svelte-spa-router", lizenz: "MIT", url: "https://github.com/ItalyPaleAle/svelte-spa-router", zweck: "Hash-basiertes Routing" },
    { name: "Font Awesome Free", lizenz: "MIT / CC BY 4.0", url: "https://github.com/FortAwesome/Font-Awesome", zweck: "Icons" },
    { name: "Barlow (Font)", lizenz: "OFL-1.1", url: "https://github.com/jpt/barlow", zweck: "Hauptschriftart" },
    { name: "JetBrains Mono (Font)", lizenz: "OFL-1.1", url: "https://github.com/JetBrains/JetBrainsMono", zweck: "Monospace-Schriftart" },
  ];

  const lizenzFarben = {
    "MIT": "var(--color-success)",
    "MIT-CMU": "var(--color-success)",
    "BSD-3-Clause": "var(--color-success)",
    "Apache-2.0": "var(--color-success)",
    "LGPL-3.0": "var(--color-warning)",
    "OFL-1.1": "var(--color-success)",
    "MIT / CC BY 4.0": "var(--color-success)",
    "GPL-3.0": "var(--color-error)",
    "AGPL-3.0": "var(--color-error)",
  };

  async function ladeMarkdown(id, pfad) {
    if (markdownInhalte[id]) return;
    try {
      const resp = await fetch(pfad);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      let text = await resp.text();
      text = text.replace("{{YEAR}}", String(new Date().getFullYear()));
      markdownInhalte = { ...markdownInhalte, [id]: text };
    } catch (e) {
      ladeFehler = { ...ladeFehler, [id]: e.message };
    }
  }

  $effect(() => {
    const section = sections.find(s => s.id === activeSection);
    if (section?.datei) {
      ladeMarkdown(section.id, section.datei);
    }
  });

  // Initiale Sektion laden
  ladeMarkdown("lizenz", "/legal/de/lizenz.md");
</script>

<div class="legal-container">
  <div class="legal-tabs">
    {#each sections as s (s.id)}
      <button
        class="legal-tab"
        class:aktiv={activeSection === s.id}
        onclick={() => activeSection = s.id}
      >
        <i class="fa-solid {s.icon}"></i>
        <span>{s.label}</span>
      </button>
    {/each}
  </div>

  <div class="legal-content">
    {#if activeSection === "drittanbieter"}
      <h3>Drittanbieter-Lizenzen</h3>
      <p>BücherFreunde verwendet die folgenden Open-Source-Bibliotheken. Die jeweiligen Lizenztexte findest du in den Quelldateien der Pakete.</p>

      <h4><i class="fa-solid fa-server"></i> Backend (Python)</h4>
      <div class="dep-tabelle">
        <div class="dep-kopf">
          <span>Bibliothek</span>
          <span>Lizenz</span>
          <span>Verwendung</span>
        </div>
        {#each backendAbhaengigkeiten as dep}
          <div class="dep-zeile">
            <a href={dep.url} target="_blank" rel="noopener" class="dep-name">{dep.name}</a>
            <span class="dep-lizenz" style="color: {lizenzFarben[dep.lizenz] || 'var(--color-text-secondary)'}">
              {dep.lizenz}
            </span>
            <span class="dep-zweck">{dep.zweck}</span>
          </div>
        {/each}
      </div>

      <h4><i class="fa-solid fa-display"></i> Frontend (JavaScript)</h4>
      <div class="dep-tabelle">
        <div class="dep-kopf">
          <span>Bibliothek</span>
          <span>Lizenz</span>
          <span>Verwendung</span>
        </div>
        {#each frontendAbhaengigkeiten as dep}
          <div class="dep-zeile">
            <a href={dep.url} target="_blank" rel="noopener" class="dep-name">{dep.name}</a>
            <span class="dep-lizenz" style="color: {lizenzFarben[dep.lizenz] || 'var(--color-text-secondary)'}">
              {dep.lizenz}
            </span>
            <span class="dep-zweck">{dep.zweck}</span>
          </div>
        {/each}
      </div>

      <div class="legende">
        <span class="legende-item"><span class="legende-dot" style="background: var(--color-success)"></span> Permissive (MIT, BSD, Apache)</span>
        <span class="legende-item"><span class="legende-dot" style="background: var(--color-warning)"></span> Schwaches Copyleft (LGPL)</span>
        <span class="legende-item"><span class="legende-dot" style="background: var(--color-error)"></span> Starkes Copyleft (AGPL, GPL)</span>
      </div>

    {:else if markdownInhalte[activeSection]}
      <div class="markdown-inhalt">
        <SvelteMarkdown source={markdownInhalte[activeSection]} />
      </div>

    {:else if ladeFehler[activeSection]}
      <div class="legal-box">
        <p>Fehler beim Laden: {ladeFehler[activeSection]}</p>
      </div>

    {:else}
      <div class="lade-anzeige">
        <i class="fa-solid fa-spinner fa-spin"></i> Lade Dokument...
      </div>
    {/if}
  </div>
</div>

<style>
  .legal-container {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .legal-tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--color-border);
    overflow-x: auto;
  }

  .legal-tab {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.75rem;
    border: none;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.8125rem;
    cursor: pointer;
    white-space: nowrap;
    border-bottom: 2px solid transparent;
    transition: all 0.15s;
  }

  .legal-tab:hover {
    color: var(--color-text-primary);
  }

  .legal-tab.aktiv {
    color: var(--color-text-primary);
    border-bottom-color: var(--color-accent);
  }

  .legal-content {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .legal-content h3 {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .legal-content h4 {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0.5rem 0 0.25rem;
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .legal-content h4 i {
    color: var(--color-accent);
    font-size: 0.75rem;
  }

  .legal-content p {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  .legal-box {
    padding: 0.75rem;
    background-color: var(--color-bg-tertiary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  /* Markdown-Inhalt Styling */
  .markdown-inhalt {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
  }

  .markdown-inhalt :global(h1) {
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 0.75rem;
    padding-bottom: 0.375rem;
    border-bottom: 1px solid var(--color-border);
  }

  .markdown-inhalt :global(h2) {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 1rem 0 0.375rem;
  }

  .markdown-inhalt :global(h3) {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0.75rem 0 0.25rem;
  }

  .markdown-inhalt :global(p) {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.6;
    margin: 0 0 0.5rem;
  }

  .markdown-inhalt :global(ul),
  .markdown-inhalt :global(ol) {
    margin: 0 0 0.5rem;
    padding-left: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .markdown-inhalt :global(li) {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .markdown-inhalt :global(strong) {
    color: var(--color-text-primary);
    font-weight: 600;
  }

  .markdown-inhalt :global(code) {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    background-color: var(--color-bg-tertiary);
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
  }

  .markdown-inhalt :global(pre) {
    background-color: var(--color-bg-tertiary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 0.75rem;
    overflow-x: auto;
    margin: 0.5rem 0;
  }

  .markdown-inhalt :global(pre code) {
    background: none;
    padding: 0;
    font-size: 0.75rem;
  }

  .markdown-inhalt :global(a) {
    color: var(--color-accent);
    text-decoration: none;
  }

  .markdown-inhalt :global(a:hover) {
    text-decoration: underline;
  }

  .markdown-inhalt :global(hr) {
    border: none;
    border-top: 1px solid var(--color-border);
    margin: 0.75rem 0;
  }

  .markdown-inhalt :global(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.75rem;
    margin: 0.5rem 0;
  }

  .markdown-inhalt :global(th) {
    background-color: var(--color-bg-secondary);
    padding: 0.375rem 0.5rem;
    text-align: left;
    font-weight: 600;
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
  }

  .markdown-inhalt :global(td) {
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary);
  }

  .markdown-inhalt :global(blockquote) {
    border-left: 3px solid var(--color-accent);
    margin: 0.5rem 0;
    padding: 0.25rem 0.75rem;
    background-color: var(--color-bg-tertiary);
    border-radius: 0 4px 4px 0;
  }

  .lade-anzeige {
    padding: 1rem;
    text-align: center;
    color: var(--color-text-muted);
    font-size: 0.8125rem;
  }

  /* Abhängigkeiten-Tabelle */
  .dep-tabelle {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    overflow: hidden;
  }

  .dep-kopf {
    display: grid;
    grid-template-columns: 1fr 0.7fr 1.5fr;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    background-color: var(--color-bg-secondary);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  .dep-zeile {
    display: grid;
    grid-template-columns: 1fr 0.7fr 1.5fr;
    gap: 0.5rem;
    padding: 0.3125rem 0.75rem;
    border-top: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
    font-size: 0.8125rem;
    align-items: center;
  }

  .dep-name {
    font-weight: 500;
    color: var(--color-accent);
    text-decoration: none;
  }

  .dep-name:hover {
    text-decoration: underline;
  }

  .dep-lizenz {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
  }

  .dep-zweck {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .legende {
    display: flex;
    gap: 1rem;
    padding: 0.5rem 0;
    flex-wrap: wrap;
  }

  .legende-item {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .legende-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
</style>
