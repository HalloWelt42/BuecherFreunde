<script>
  import { kiStatus, healthCheck, ladeConfig } from "../../api/config.js";
  import { onMount } from "svelte";

  let services = $state([]);
  let laden = $state(true);
  let aktiverTab = $state(0);

  const dienstInfos = {
    "Backend API": {
      beschreibung: "FastAPI-Backend für alle Buchverwaltungsoperationen. Stellt REST-API bereit für Bücher, Kategorien, Suche, Import und Konfiguration.",
      feldmapping: null,
    },
    "Frontend": {
      beschreibung: "Svelte 5 Single-Page-Application. Kommuniziert ausschließlich über die Backend-API per Bearer Token.",
      feldmapping: null,
    },
    "Google Books": {
      beschreibung: "Primäre Metadatenquelle von Google. Liefert Titel, Autor, Verlag, ISBN, Beschreibung, Cover, Kategorien und weitere bibliografische Daten. Ohne API-Key eingeschränkt (geteiltes Rate-Limit).",
      url: "https://www.googleapis.com/books/v1",
      feldmapping: [
        { api: "volumeInfo.title", lokal: "titel" },
        { api: "volumeInfo.authors", lokal: "autor" },
        { api: "volumeInfo.publisher", lokal: "verlag" },
        { api: "volumeInfo.publishedDate", lokal: "jahr" },
        { api: "volumeInfo.pageCount", lokal: "seiten" },
        { api: "volumeInfo.industryIdentifiers", lokal: "isbn" },
        { api: "volumeInfo.language", lokal: "sprache" },
        { api: "volumeInfo.description", lokal: "beschreibung" },
        { api: "volumeInfo.categories", lokal: "kategorien" },
        { api: "volumeInfo.imageLinks", lokal: "cover_url" },
      ],
      raw: ["untertitel", "erscheinungsdatum", "identifiers", "lesemodi", "altersfreigabe", "inhaltsversion", "vorschau_link", "info_link", "google_books_link", "durchschnittsbewertung", "anzahl_bewertungen", "abmessungen"],
    },
    "Open Library": {
      beschreibung: "Offene Bibliotheksdatenbank. Nutzt Bibkeys-API und Edition-API. Liefert umfangreiche Metadaten inklusive Subjects, Excerpts und Links. Rate-Limit konfigurierbar.",
      url: "https://openlibrary.org/api",
      feldmapping: [
        { api: "title", lokal: "titel" },
        { api: "authors[].name", lokal: "autor" },
        { api: "publishers[].name", lokal: "verlag" },
        { api: "publish_date", lokal: "jahr" },
        { api: "number_of_pages", lokal: "seiten" },
        { api: "identifiers", lokal: "isbn" },
        { api: "subjects/subject_*", lokal: "kategorien" },
        { api: "cover.large", lokal: "cover_url" },
      ],
      raw: ["identifiers", "excerpts", "links", "subjects", "subject_places", "subject_people", "subject_times"],
    },
    "Wikipedia/Wikidata": {
      beschreibung: "Strukturierte Daten aus Wikidata und Beschreibungstexte aus Wikipedia. Suche über ISBN (P212/P957) für Bücher und über Namens-Match mit Konfidenz-Scoring für Autoren. Liefert Metadaten, Biografien und Werklisten.",
      url: "https://www.wikidata.org/w/api.php",
      feldmapping: [
        { api: "labels (de/en)", lokal: "titel" },
        { api: "P50 (Autor)", lokal: "autor" },
        { api: "P123 (Verlag)", lokal: "verlag" },
        { api: "P577 (Erscheinungsdatum)", lokal: "jahr" },
        { api: "P1104 (Seitenanzahl)", lokal: "seiten" },
        { api: "P212/P957 (ISBN)", lokal: "isbn" },
        { api: "P407 (Sprache)", lokal: "sprache" },
        { api: "dewiki Extrakt", lokal: "beschreibung" },
        { api: "P136 (Genre) + P921 (Thema)", lokal: "kategorien" },
      ],
      autorenmapping: [
        { api: "P106 (Beruf)", lokal: "konfidenz (+10 Pkt.)" },
        { api: "Name-Match", lokal: "konfidenz (+8 Pkt.)" },
        { api: "dewiki Sitelink", lokal: "konfidenz (+5 Pkt.)" },
        { api: "Sitelinks (Anzahl)", lokal: "konfidenz (+1-10 Pkt.)" },
        { api: "P800 (Werke) vs. Bibliothek", lokal: "konfidenz (+15 Pkt.)" },
        { api: "ISBN-Match in Werken", lokal: "konfidenz (+30 Pkt.)" },
        { api: "dewiki Volltext", lokal: "biografie (Markdown)" },
        { api: "P18 (Bild)", lokal: "foto (3 Größen)" },
        { api: "P800 (notable works)", lokal: "werke-liste" },
        { api: "P27 (Staatsangehörigkeit)", lokal: "nationalität" },
        { api: "P569/P570 (Geburt/Tod)", lokal: "geburts-/todesjahr" },
      ],
      raw: ["wikidata_id", "kurzbeschreibung", "isbn13", "isbn10", "autoren", "verlage", "sprachen", "genres", "themen", "typen", "wikipedia_titel", "sitelinks"],
      konfidenz: "Hoch: ab 15 Pkt. oder Buch/ISBN-Treffer | Mittel: 8-14 Pkt. | Niedrig: unter 8 Pkt.",
    },
    "LM Studio": {
      beschreibung: "Lokale KI für automatische Buchkategorisierung. OpenAI-kompatible API auf konfigurierbarem Host. Analysiert Titel, Autor und Textauszug und schlägt Kategorien mit Konfidenzwerten vor.",
      feldmapping: [
        { api: "KI-Analyse", lokal: "kategorien (Vorschläge mit Konfidenz)" },
      ],
      raw: null,
    },
    "Gutenberg (Gutendex)": {
      beschreibung: "JSON-API für Project Gutenberg (gutendex.com). Ermöglicht Suche, Vorschau und Import gemeinfreier Bücher. Unterstützt Sprachfilter und liefert EPUB- und TXT-Downloads.",
      url: "https://gutendex.com",
      feldmapping: [
        { api: "id", lokal: "gutenberg_id" },
        { api: "title", lokal: "titel" },
        { api: "authors[].name", lokal: "autor" },
        { api: "languages[]", lokal: "sprachen" },
        { api: "formats (epub/txt)", lokal: "download_url" },
        { api: "formats (image/jpeg)", lokal: "cover" },
        { api: "bookshelves[]", lokal: "regale" },
        { api: "subjects[]", lokal: "themen" },
        { api: "download_count", lokal: "download_anzahl" },
      ],
      raw: ["gutenberg_id", "sprachen", "regale", "themen"],
    },
  };

  onMount(() => {
    pruefeServices();
  });

  async function pruefeServices() {
    laden = true;
    const ergebnisse = [];
    let config = null;

    // Backend
    try {
      const health = await healthCheck();
      ergebnisse.push({
        name: "Backend API",
        icon: "fa-server",
        status: "online",
        info: `v${health.version}`,
        url: window.location.origin + "/api",
      });
    } catch {
      ergebnisse.push({
        name: "Backend API",
        icon: "fa-server",
        status: "offline",
        info: "Nicht erreichbar",
        url: null,
      });
    }

    // Konfiguration laden
    try {
      config = await ladeConfig();
    } catch { /* still */ }

    if (config) {
      // Frontend
      ergebnisse.push({
        name: "Frontend",
        icon: "fa-display",
        status: "online",
        info: `Port ${config.external_port}`,
        url: `http://localhost:${config.external_port}`,
      });

      // Google Books
      ergebnisse.push({
        name: "Google Books",
        icon: "fa-g",
        status: config.google_books?.aktiviert ? "online" : "deaktiviert",
        info: config.google_books?.aktiviert
          ? config.google_books.hat_api_key ? "Mit API-Key" : "Ohne API-Key (eingeschränkt)"
          : "Deaktiviert",
        url: "https://www.googleapis.com/books/v1",
        config: config.google_books,
      });

      // Open Library
      ergebnisse.push({
        name: "Open Library",
        icon: "fa-book-open",
        status: config.openlibrary?.aktiviert ? "online" : "deaktiviert",
        info: config.openlibrary?.aktiviert
          ? `Rate-Limit: ${config.openlibrary.rate_limit}/s`
          : "Deaktiviert",
        url: "https://openlibrary.org/api",
        config: config.openlibrary,
      });

      // Wikipedia/Wikidata
      ergebnisse.push({
        name: "Wikipedia/Wikidata",
        icon: "fa-w",
        status: config.wikipedia?.aktiviert ? "online" : "deaktiviert",
        info: config.wikipedia?.aktiviert ? "Wikidata SPARQL + Wikipedia Extracts" : "Deaktiviert",
        url: "https://www.wikidata.org/w/api.php",
        config: config.wikipedia,
      });

      // LM Studio
      if (config.lm_studio?.aktiviert) {
        try {
          const ki = await kiStatus();
          ergebnisse.push({
            name: "LM Studio",
            icon: "fa-robot",
            status: ki.erreichbar ? "online" : "offline",
            info: ki.erreichbar ? `Modell: ${ki.modell}` : "Nicht erreichbar",
            url: config.lm_studio.url,
            config: config.lm_studio,
          });
        } catch {
          ergebnisse.push({
            name: "LM Studio",
            icon: "fa-robot",
            status: "offline",
            info: "Nicht erreichbar",
            url: config.lm_studio.url,
            config: config.lm_studio,
          });
        }
      } else {
        ergebnisse.push({
          name: "LM Studio",
          icon: "fa-robot",
          status: "deaktiviert",
          info: "Deaktiviert",
          url: config.lm_studio?.url || null,
          config: config.lm_studio,
        });
      }

      // Gutenberg (Gutendex)
      try {
        const res = await fetch("https://gutendex.com/books/?page=1&search=test");
        ergebnisse.push({
          name: "Gutenberg (Gutendex)",
          icon: "fa-landmark-dome",
          status: res.ok ? "online" : "offline",
          info: res.ok ? "Gutendex-API erreichbar" : `HTTP ${res.status}`,
          url: "https://gutendex.com",
        });
      } catch {
        ergebnisse.push({
          name: "Gutenberg (Gutendex)",
          icon: "fa-landmark-dome",
          status: "offline",
          info: "Nicht erreichbar",
          url: "https://gutendex.com",
        });
      }
    }

    services = ergebnisse;
    laden = false;
  }

  const statusColors = {
    online: "var(--color-success)",
    offline: "var(--color-error)",
    deaktiviert: "var(--color-text-muted)",
  };
</script>

<div class="svc-container">
  {#if laden}
    <p class="svc-loading"><i class="fa-solid fa-spinner fa-spin"></i> Dienste werden geprüft...</p>
  {:else}
    <div class="svc-tabs">
      {#each services as svc, i (svc.name)}
        <button
          class="svc-tab"
          class:aktiv={aktiverTab === i}
          onclick={() => aktiverTab = i}
        >
          <span
            class="tab-dot"
            style="background-color: {statusColors[svc.status] || 'var(--color-text-muted)'}"
          ></span>
          <i class="fa-solid {svc.icon} tab-icon"></i>
          <span class="tab-name">{svc.name}</span>
        </button>
      {/each}
    </div>

    {#if services[aktiverTab]}
      {@const svc = services[aktiverTab]}
      {@const info = dienstInfos[svc.name]}
      <div class="svc-detail">
        <div class="svc-header">
          <span class="svc-status-label" style="color: {statusColors[svc.status]}">
            {svc.status === "online" ? "Verbunden" : svc.status === "offline" ? "Nicht erreichbar" : "Deaktiviert"}
          </span>
          <span class="svc-info-text">{svc.info}</span>
        </div>

        {#if svc.url}
          <code class="svc-url">{svc.url}</code>
        {/if}

        {#if info?.beschreibung}
          <p class="svc-beschreibung">{info.beschreibung}</p>
        {/if}

        {#if info?.feldmapping}
          <div class="mapping-section">
            <h4 class="mapping-titel">Feldmapping</h4>
            <div class="mapping-tabelle">
              <div class="mapping-kopf">
                <span>API-Feld</span>
                <span>Lokales Feld</span>
              </div>
              {#each info.feldmapping as m}
                <div class="mapping-zeile">
                  <code class="mapping-api">{m.api}</code>
                  <span class="mapping-lokal">{m.lokal}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if info?.autorenmapping}
          <div class="mapping-section">
            <h4 class="mapping-titel">Autoren-Anreicherung</h4>
            <div class="mapping-tabelle">
              <div class="mapping-kopf">
                <span>Quelle</span>
                <span>Ziel</span>
              </div>
              {#each info.autorenmapping as m}
                <div class="mapping-zeile">
                  <code class="mapping-api">{m.api}</code>
                  <span class="mapping-lokal">{m.lokal}</span>
                </div>
              {/each}
            </div>
            {#if info.konfidenz}
              <p class="konfidenz-erklaerung">{info.konfidenz}</p>
            {/if}
          </div>
        {/if}

        {#if info?.raw}
          <div class="raw-info">
            <h4 class="mapping-titel">Zusätzliche Rohdaten</h4>
            <div class="raw-felder">
              {#each info.raw as feld}
                <code class="raw-feld">{feld}</code>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <button class="svc-refresh" onclick={pruefeServices}>
      <i class="fa-solid fa-rotate"></i> Neu prüfen
    </button>
  {/if}
</div>

<style>
  .svc-container {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .svc-loading {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  /* Tabs */
  .svc-tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--color-border);
    overflow-x: auto;
  }

  .svc-tab {
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

  .svc-tab:hover {
    color: var(--color-text-primary);
    background-color: var(--color-bg-tertiary);
  }

  .svc-tab.aktiv {
    color: var(--color-text-primary);
    border-bottom-color: var(--color-accent);
  }

  .tab-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .tab-icon {
    font-size: 0.75rem;
    width: 1rem;
    text-align: center;
  }

  .tab-name {
    font-weight: 500;
  }

  /* Detail */
  .svc-detail {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
    padding: 0.75rem;
    background-color: var(--color-bg-tertiary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
  }

  .svc-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .svc-status-label {
    font-size: 0.8125rem;
    font-weight: 600;
  }

  .svc-info-text {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .svc-url {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background-color: var(--color-bg-primary);
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    border: 1px solid var(--color-border);
    word-break: break-all;
  }

  .svc-beschreibung {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
    margin: 0;
  }

  /* Feldmapping */
  .mapping-section, .raw-info {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .mapping-titel {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    margin: 0;
  }

  .mapping-tabelle {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    overflow: hidden;
  }

  .mapping-kopf {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    padding: 0.375rem 0.5rem;
    background-color: var(--color-bg-secondary);
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-text-muted);
  }

  .mapping-zeile {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    border-top: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
    font-size: 0.8125rem;
    align-items: center;
  }

  .mapping-api {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .mapping-lokal {
    color: var(--color-text-primary);
    font-weight: 500;
  }

  /* Raw-Felder */
  .raw-felder {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .raw-feld {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
    background-color: var(--color-bg-secondary);
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
    border: 1px solid var(--color-border);
  }

  .konfidenz-erklaerung {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin-top: 0.5rem;
    padding: 0.375rem 0.5rem;
    background-color: var(--color-bg-secondary);
    border-radius: 4px;
    border-left: 3px solid var(--color-accent);
  }

  /* Refresh */
  .svc-refresh {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    align-self: flex-start;
    transition: all 0.1s;
  }

  .svc-refresh:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }
</style>
