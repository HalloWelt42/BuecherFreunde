<script>
  let activeSection = $state("lizenz");

  const sections = [
    { id: "lizenz", label: "Lizenz", icon: "fa-scale-balanced" },
    { id: "agb", label: "AGB", icon: "fa-file-contract" },
    { id: "drittanbieter", label: "Drittanbieter", icon: "fa-cubes" },
    { id: "datenschutz", label: "Datenschutz", icon: "fa-shield-halved" },
    { id: "haftung", label: "Haftungsausschluss", icon: "fa-triangle-exclamation" },
    { id: "info", label: "Info", icon: "fa-circle-info" },
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
    {#if activeSection === "lizenz"}
      <h3>AGPL-3.0 -- GNU Affero General Public License</h3>
      <p>
        BücherFreunde ist freie Software unter der <strong>GNU Affero General Public License, Version 3</strong> (AGPL-3.0).
      </p>
      <div class="legal-box">
        <p>Du darfst diese Software frei nutzen, kopieren, verändern und weitergeben -- unter folgenden Bedingungen:</p>
        <ul>
          <li><strong>Quellcode-Pflicht:</strong> Wenn du die Software veränderst und als Netzwerkdienst anbietest, musst du den vollständigen Quellcode veröffentlichen.</li>
          <li><strong>Copyleft:</strong> Abgeleitete Werke müssen ebenfalls unter AGPL-3.0 stehen.</li>
          <li><strong>Keine Garantie:</strong> Die Software wird ohne jede Gewährleistung bereitgestellt.</li>
          <li><strong>Namensnennung:</strong> Der ursprüngliche Copyright-Hinweis muss erhalten bleiben.</li>
        </ul>
      </div>
      <div class="legal-meta">
        <div class="meta-row">
          <span class="meta-label">Lizenz</span>
          <span class="meta-value">AGPL-3.0-or-later</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Copyright</span>
          <span class="meta-value">2024-2026 HalloWelt42</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Repository</span>
          <code class="meta-value mono">github.com/HalloWelt42/BuecherFreunde</code>
        </div>
        <div class="meta-row">
          <span class="meta-label">Lizenztext</span>
          <span class="meta-value"><a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noopener" class="meta-link">gnu.org/licenses/agpl-3.0.html</a></span>
        </div>
      </div>


    {:else if activeSection === "agb"}
      <h3>Nutzungsbedingungen</h3>
      <div class="legal-box">
        <h4>Geltungsbereich</h4>
        <p>Diese Bedingungen gelten für die Nutzung der BücherFreunde Software.</p>
      </div>
      <div class="legal-box">
        <h4>Nutzung</h4>
        <ul>
          <li>BücherFreunde ist eine selbst gehostete Buchverwaltung für den persönlichen Gebrauch.</li>
          <li>Die Software wird unter der AGPL-3.0 Lizenz bereitgestellt und darf gemäß deren Bedingungen genutzt, verändert und weiterverbreitet werden.</li>
          <li>Die Nutzung erfolgt auf eigene Verantwortung.</li>
          <li>Der Nutzer ist für die Einhaltung des Urheberrechts bei importierten Dateien selbst verantwortlich.</li>
        </ul>
      </div>
      <div class="legal-box">
        <h4>Haftung</h4>
        <p>Der Entwickler übernimmt keine Haftung für:</p>
        <ul>
          <li>Schäden, die durch die Nutzung der Software entstehen</li>
          <li>Datenverlust durch fehlerhafte Konfiguration, Hardware-Ausfälle oder Bedienfehler</li>
          <li>Die Richtigkeit von Metadaten aus externen Quellen (Open Library, Google Books, Wikipedia, Gutendex)</li>
          <li>Inhalte gemeinfreier Bücher, die über Project Gutenberg importiert werden</li>
        </ul>
      </div>
      <div class="legal-box">
        <h4>Externe Dienste</h4>
        <p>BücherFreunde kann optional externe Dienste nutzen (Open Library, Google Books, Wikipedia/Wikidata, Gutendex, LM Studio). Für deren Nutzung gelten die jeweiligen Nutzungsbedingungen. Alle Verbindungen können in den Einstellungen deaktiviert werden.</p>
      </div>
      <div class="legal-box">
        <h4>Backups</h4>
        <p>Der Nutzer ist selbst für regelmäßige Backups seiner Daten verantwortlich.</p>
      </div>

    {:else if activeSection === "drittanbieter"}
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

    {:else if activeSection === "datenschutz"}
      <h3>Datenschutz</h3>
      <p>BücherFreunde ist eine selbst gehostete Anwendung. Deine Daten verlassen deinen Server nur in den folgenden Fällen:</p>

      <div class="legal-box">
        <h4>Externe Verbindungen</h4>
        <ul>
          <li><strong>Open Library</strong> (openlibrary.org) -- Metadaten-Abfrage per ISBN/Titel. Sendet: ISBN, Titel, Autor. Empfängt: Bibliografische Daten.</li>
          <li><strong>Google Books</strong> (googleapis.com) -- Metadaten-Abfrage. Sendet: ISBN, Titel. Empfängt: Bibliografische Daten, Cover-URLs.</li>
          <li><strong>Wikipedia/Wikidata</strong> (wikidata.org, wikipedia.org) -- Autoren-Anreicherung. Sendet: Autorennamen, ISBN. Empfängt: Biografien, Fotos, Werklisten.</li>
          <li><strong>Gutendex</strong> (gutendex.com) -- Gutenberg-Suche und -Download. Sendet: Suchbegriffe. Empfängt: Buchdaten, Dateien.</li>
          <li><strong>GitHub</strong> (raw.githubusercontent.com) -- Update-Prüfung. Sendet: nichts Personenbezogenes. Empfängt: Versionsnummer.</li>
          <li><strong>LM Studio</strong> (konfigurierbar) -- KI-Kategorisierung. Sendet: Titel, Autor, Textauszug. Empfängt: Kategorie-Vorschläge. Nur bei aktivierter KI, nur an die konfigurierte Adresse.</li>
        </ul>
      </div>

      <div class="legal-box">
        <h4>Lokale Datenhaltung</h4>
        <ul>
          <li>Alle Buchdateien, Metadaten, Notizen, Markierungen und Einstellungen werden ausschließlich lokal auf deinem Server gespeichert.</li>
          <li>Es gibt keine Benutzerkonten, keine Registrierung und keine Analytik.</li>
          <li>Der API-Token wird nur lokal im Browser (localStorage) gespeichert.</li>
          <li>Es werden keine Cookies gesetzt.</li>
        </ul>
      </div>

      <div class="legal-box">
        <h4>Externe Dienste deaktivieren</h4>
        <p>Alle externen Verbindungen können in den Einstellungen oder der <code>.env</code>-Datei einzeln deaktiviert werden. Die Anwendung funktioniert vollständig offline -- nur Metadaten-Anreicherung, Gutenberg-Import und Update-Check benötigen Internet.</p>
      </div>

    {:else if activeSection === "haftung"}
      <h3>Haftungsausschluss</h3>
      <div class="legal-box">
        <p>
          BücherFreunde wird <strong>"wie besehen"</strong> (as is) und ohne jede Gewährleistung bereitgestellt, weder ausdrücklich noch stillschweigend.
        </p>
        <ul>
          <li>Der Autor übernimmt keine Haftung für Schäden, die durch die Nutzung der Software entstehen.</li>
          <li>Die Software ist für den persönlichen, nicht-kommerziellen Gebrauch auf eigener Hardware gedacht.</li>
          <li>Der Nutzer ist selbst für Backups seiner Daten verantwortlich.</li>
          <li>Für die über externe APIs abgerufenen Daten (Metadaten, Cover, Gutenberg-Bücher) gelten die jeweiligen Nutzungsbedingungen der Anbieter.</li>
          <li>Project Gutenberg-Bücher sind gemeinfrei. Die Nutzung unterliegt den Bedingungen von <code>gutenberg.org</code>.</li>
        </ul>
      </div>

      <div class="legal-box">
        <h4>Urheberrecht</h4>
        <p>BücherFreunde ist ein Werkzeug zur Verwaltung eigener Bücher und Dokumente. Der Nutzer ist dafür verantwortlich, dass er die Rechte an den importierten Dateien besitzt oder diese gemeinfrei sind. Die Software prüft keine Urheberrechte.</p>
      </div>

    {:else if activeSection === "info"}
      <h3>Projektinformationen</h3>
      <div class="legal-meta">
        <div class="meta-row">
          <span class="meta-label">Projekt</span>
          <span class="meta-value">BücherFreunde</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Autor</span>
          <span class="meta-value">HalloWelt42</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Lizenz</span>
          <span class="meta-value">AGPL-3.0-or-later</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Repository</span>
          <code class="meta-value mono">github.com/HalloWelt42/BuecherFreunde</code>
        </div>
        <div class="meta-row">
          <span class="meta-label">Zweck</span>
          <span class="meta-value">Selbst gehostete Buchverwaltung für 50.000+ Bücher</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Plattformen</span>
          <span class="meta-value">Raspberry Pi 5, Mac, Linux (Docker)</span>
        </div>
      </div>

      <div class="legal-box">
        <h4>Technologie-Stack</h4>
        <ul>
          <li><strong>Frontend:</strong> Svelte 5 + Vite + Tailwind CSS 4</li>
          <li><strong>Backend:</strong> Python FastAPI + Uvicorn</li>
          <li><strong>Datenbank:</strong> SQLite + FTS5 (Volltextsuche)</li>
          <li><strong>PDF:</strong> PyMuPDF (Canvas + TextLayer)</li>
          <li><strong>EPUB/MOBI:</strong> foliate-js + EbookLib</li>
          <li><strong>Metadaten:</strong> Open Library, Google Books, Wikipedia/Wikidata</li>
          <li><strong>KI:</strong> LM Studio (lokal, optional)</li>
          <li><strong>Container:</strong> Docker Compose (python:3.12-slim, nginx:alpine)</li>
        </ul>
      </div>

      <div class="legal-box">
        <h4>Originale Rechtsdokumente</h4>
        <p>Die rechtlichen Dokumente dieses Projekts basieren auf den Vorlagen von RadioHub:</p>
        <a href="https://github.com/HalloWelt42/RadioHub/tree/main/radiohub-frontend/public/legal/de" target="_blank" rel="noopener" class="datei-link" style="margin-top: 0.25rem">
          <i class="fa-brands fa-github"></i> RadioHub -- Rechtliche Dokumente (Original)
        </a>
      </div>

      <p class="legal-hinweis">
        Alle Dokumente liegen auch als Markdown-Dateien unter <code>/legal/de/</code> im Projektverzeichnis.
      </p>
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

  .legal-box h4 {
    margin: 0;
  }

  .legal-box ul {
    margin: 0;
    padding-left: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .legal-box li {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }

  .legal-box code {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    background-color: var(--color-bg-secondary);
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
  }

  .legal-meta {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.75rem;
    background-color: var(--color-bg-tertiary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
  }

  .meta-row {
    display: flex;
    gap: 0.75rem;
    font-size: 0.8125rem;
    align-items: baseline;
  }

  .meta-label {
    font-weight: 600;
    color: var(--color-text-muted);
    min-width: 6rem;
    flex-shrink: 0;
  }

  .meta-value {
    color: var(--color-text-primary);
  }

  .meta-value.mono {
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .meta-value code {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    background-color: var(--color-bg-secondary);
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
  }

  .meta-link {
    color: var(--color-accent);
    text-decoration: none;
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .meta-link:hover {
    text-decoration: underline;
  }

  .legal-hinweis {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-style: italic;
    padding: 0.5rem 0.75rem;
    border-left: 3px solid var(--color-accent);
    background-color: var(--color-bg-tertiary);
    border-radius: 0 4px 4px 0;
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

  /* Datei-Link */
  .datei-link {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--color-accent);
    text-decoration: none;
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    transition: all 0.1s;
  }

  .datei-link:hover {
    border-color: var(--color-accent);
    background-color: color-mix(in srgb, var(--color-accent) 10%, transparent);
  }
</style>
