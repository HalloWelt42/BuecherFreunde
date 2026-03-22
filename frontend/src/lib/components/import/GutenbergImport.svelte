<script>
  import { get, post, del, getToken } from "../../api/client.js";
  import { onDestroy } from "svelte";
  import { notifyBooksChanged } from "../../stores/processes.svelte.js";

  let suchbegriff = $state("");
  let sprache = $state("de");
  let ergebnisse = $state([]);
  let gesamt = $state(0);
  let seite = $state(1);
  let laden = $state(false);
  let fehler = $state(null);

  // Auswahl
  let ausgewaehlt = $state(new Set());

  // Import-Status
  let importLaeuft = $state(false);
  let importStatus = $state(null);
  let sseConnection = $state(null);

  onDestroy(() => {
    sseConnection?.close();
  });

  async function suchen(neueSuche = true) {
    if (neueSuche) {
      seite = 1;
      ausgewaehlt = new Set();
    }
    laden = true;
    fehler = null;
    try {
      const params = new URLSearchParams();
      if (suchbegriff.trim()) params.set("q", suchbegriff.trim());
      if (sprache.trim()) params.set("sprache", sprache.trim());
      params.set("seite", seite);
      const data = await get(`/api/gutenberg/suche?${params}`);
      ergebnisse = data.buecher || [];
      gesamt = data.gesamt || 0;
    } catch (e) {
      fehler = e.message || "Suche fehlgeschlagen";
      ergebnisse = [];
    } finally {
      laden = false;
    }
  }

  function toggleAuswahl(buch) {
    const id = buch.gutenberg_id;
    const neu = new Set(ausgewaehlt);
    if (neu.has(id)) {
      neu.delete(id);
    } else {
      neu.add(id);
    }
    ausgewaehlt = neu;
  }

  function alleAuswaehlen() {
    if (ausgewaehlt.size === ergebnisse.length) {
      ausgewaehlt = new Set();
    } else {
      ausgewaehlt = new Set(ergebnisse.map(b => b.gutenberg_id));
    }
  }

  async function importStarten() {
    if (ausgewaehlt.size === 0) return;
    fehler = null;
    importLaeuft = true;

    const buecher = ergebnisse
      .filter(b => ausgewaehlt.has(b.gutenberg_id))
      .map(b => ({
        gutenberg_id: b.gutenberg_id,
        titel: b.titel,
        autor: b.autor,
        download_url: b.download_url,
        download_format: b.download_format,
        cover_url: b.cover_url,
      }));

    try {
      await post("/api/gutenberg/import", { buecher });
      starteSSE();
    } catch (e) {
      fehler = e.message || "Import-Start fehlgeschlagen";
      importLaeuft = false;
    }
  }

  function starteSSE() {
    sseConnection?.close();
    const token = getToken();
    const url = `/api/gutenberg/import/events?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        importStatus = data;
        if (!data.laeuft && data.gesamt > 0) {
          importLaeuft = false;
          es.close();
          notifyBooksChanged();
        }
      } catch {}
    };

    es.onerror = () => {
      setTimeout(() => {
        if (importLaeuft) starteSSE();
      }, 3000);
    };

    sseConnection = es;
  }

  async function importZuruecksetzen() {
    try {
      await del("/api/gutenberg/import/reset");
      importStatus = null;
    } catch {}
  }

  let fortschrittProzent = $derived(
    importStatus && importStatus.gesamt > 0
      ? Math.round((importStatus.fertig / importStatus.gesamt) * 100)
      : 0
  );

  function formatSprachen(sprachen) {
    const namen = { de: "Deutsch", en: "Englisch", fr: "Französisch", es: "Spanisch", it: "Italienisch", la: "Latein", nl: "Niederländisch", pt: "Portugiesisch" };
    return (sprachen || []).map(s => namen[s] || s).join(", ");
  }
</script>

<div class="gutenberg-section">
  <div class="section-header">
    <h2><i class="fa-solid fa-landmark-dome"></i> Project Gutenberg</h2>
    <span class="section-hint">Gemeinfreie Bücher kostenlos importieren</span>
  </div>

  <!-- Suchformular -->
  <div class="search-form">
    <div class="search-row">
      <input
        type="text"
        class="search-input"
        placeholder="Titel, Autor..."
        bind:value={suchbegriff}
        onkeydown={(e) => e.key === "Enter" && suchen()}
      />
      <div class="sprache-wrapper">
        <label for="gutenberg-sprache">Sprache</label>
        <input
          id="gutenberg-sprache"
          type="text"
          class="sprache-input"
          placeholder="de, en, de,en"
          bind:value={sprache}
        />
      </div>
      <button class="action-btn primary" onclick={() => suchen()} disabled={laden}>
        {#if laden}
          <i class="fa-solid fa-spinner fa-spin"></i>
        {:else}
          <i class="fa-solid fa-search"></i>
        {/if}
        Suchen
      </button>
    </div>
  </div>

  {#if fehler}
    <div class="error-banner">
      <p>{fehler}</p>
    </div>
  {/if}

  <!-- Import-Fortschritt -->
  {#if importStatus && (importLaeuft || importStatus.gesamt > 0)}
    <div class="import-progress-section">
      <div class="progress-header">
        <span class="progress-title">
          {#if importLaeuft}
            <i class="fa-solid fa-spinner fa-spin"></i> Import läuft...
          {:else}
            <i class="fa-solid fa-check-circle"></i> Import abgeschlossen
          {/if}
        </span>
        <span class="progress-counts">
          {importStatus.fertig} / {importStatus.gesamt}
          {#if importStatus.duplikate > 0}
            <span class="badge badge-warn">{importStatus.duplikate} Duplikate</span>
          {/if}
          {#if importStatus.fehler > 0}
            <span class="badge badge-error">{importStatus.fehler} Fehler</span>
          {/if}
        </span>
      </div>

      <div class="progress-bar-outer">
        <div class="progress-bar-inner" style="width: {fortschrittProzent}%"></div>
      </div>

      {#if importStatus.aktuell && importLaeuft}
        <div class="progress-current">
          <i class="fa-solid fa-download"></i> {importStatus.aktuell}
        </div>
      {/if}

      <!-- Einzelergebnisse -->
      {#if importStatus.ergebnisse && importStatus.ergebnisse.length > 0}
        <div class="import-results">
          {#each importStatus.ergebnisse as erg}
            <div class="import-result-item" class:ok={erg.status === "ok"} class:duplikat={erg.status === "duplikat"} class:fehler={erg.status === "fehler"}>
              <span class="result-icon">
                {#if erg.status === "ok"}
                  <i class="fa-solid fa-check"></i>
                {:else if erg.status === "duplikat"}
                  <i class="fa-solid fa-clone"></i>
                {:else}
                  <i class="fa-solid fa-xmark"></i>
                {/if}
              </span>
              <span class="result-title">{erg.titel}</span>
              <span class="result-detail">{erg.detail}</span>
            </div>
          {/each}
        </div>
      {/if}

      {#if !importLaeuft}
        <button class="action-btn" onclick={importZuruecksetzen}>
          <i class="fa-solid fa-broom"></i> Zurücksetzen
        </button>
      {/if}
    </div>
  {/if}

  <!-- Suchergebnisse -->
  {#if ergebnisse.length > 0}
    <div class="results-header">
      <span class="results-count">{gesamt} Treffer (Seite {seite})</span>
      <div class="results-actions">
        <button class="action-btn" onclick={alleAuswaehlen}>
          {#if ausgewaehlt.size === ergebnisse.length}
            Keine auswählen
          {:else}
            Alle auswählen
          {/if}
        </button>
        {#if ausgewaehlt.size > 0}
          <button class="action-btn primary" onclick={importStarten} disabled={importLaeuft}>
            <i class="fa-solid fa-download"></i>
            {ausgewaehlt.size} importieren
          </button>
        {/if}
      </div>
    </div>

    <div class="results-list">
      {#each ergebnisse as buch (buch.gutenberg_id)}
        <button
          class="result-card"
          class:selected={ausgewaehlt.has(buch.gutenberg_id)}
          onclick={() => toggleAuswahl(buch)}
        >
          <div class="result-check">
            {#if ausgewaehlt.has(buch.gutenberg_id)}
              <i class="fa-solid fa-square-check"></i>
            {:else}
              <i class="fa-regular fa-square"></i>
            {/if}
          </div>

          {#if buch.cover_url}
            <img class="result-cover" src={buch.cover_url} alt="" loading="lazy" />
          {:else}
            <div class="result-cover result-cover-placeholder">
              <i class="fa-solid fa-book"></i>
            </div>
          {/if}

          <div class="result-info">
            <div class="result-titel">{buch.titel}</div>
            {#if buch.autor}
              <div class="result-autor">{buch.autor}</div>
            {/if}
            <div class="result-meta">
              {#if buch.sprachen && buch.sprachen.length > 0}
                <span class="meta-tag">{formatSprachen(buch.sprachen)}</span>
              {/if}
              {#if buch.download_format}
                <span class="meta-tag format">{buch.download_format.toUpperCase()}</span>
              {/if}
              {#if buch.download_count > 0}
                <span class="meta-tag"><i class="fa-solid fa-download"></i> {buch.download_count}</span>
              {/if}
            </div>
          </div>
        </button>
      {/each}
    </div>

    <!-- Paginierung -->
    <div class="pagination">
      <button class="action-btn" onclick={() => { seite--; suchen(false); }} disabled={seite <= 1 || laden}>
        <i class="fa-solid fa-chevron-left"></i> Zurück
      </button>
      <span class="page-info">Seite {seite}</span>
      <button class="action-btn" onclick={() => { seite++; suchen(false); }} disabled={ergebnisse.length < 32 || laden}>
        Weiter <i class="fa-solid fa-chevron-right"></i>
      </button>
    </div>
  {:else if !laden && gesamt === 0 && suchbegriff}
    <div class="empty-state">
      <i class="fa-solid fa-search"></i>
      <p>Keine Ergebnisse für "{suchbegriff}"</p>
    </div>
  {/if}
</div>

<style>
  .gutenberg-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .section-header {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
  }

  .section-header h2 {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .section-hint {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  /* Suchformular */
  .search-form {
    padding: 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
  }

  .search-row {
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
  }

  .search-input {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
  }

  .sprache-wrapper {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .sprache-wrapper label {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-weight: 500;
  }

  .sprache-input {
    width: 90px;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
  }

  .action-btn {
    padding: 0.5rem 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    color: var(--color-text-primary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: background-color 0.15s;
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
  }

  .action-btn:hover:not(:disabled) {
    background: var(--glass-bg-btn);
  }

  .action-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .action-btn.primary {
    background: var(--color-accent);
    color: #fff;
    border-color: var(--color-accent);
  }

  .action-btn.primary:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .error-banner {
    padding: 0.75rem 1rem;
    border: 1px solid var(--color-error);
    border-radius: 8px;
    background-color: color-mix(in srgb, var(--color-error) 10%, transparent);
    color: var(--color-error);
    font-size: 0.875rem;
  }

  /* Import-Fortschritt */
  .import-progress-section {
    padding: 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    background: var(--glass-bg);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .progress-title {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .progress-counts {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .badge {
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
  }

  .badge-warn {
    background: color-mix(in srgb, var(--color-warning) 20%, transparent);
    color: var(--color-warning);
  }

  .badge-error {
    background: color-mix(in srgb, var(--color-error) 20%, transparent);
    color: var(--color-error);
  }

  .progress-bar-outer {
    height: 6px;
    background: var(--color-bg-tertiary);
    border-radius: 3px;
    overflow: hidden;
  }

  .progress-bar-inner {
    height: 100%;
    background: var(--color-accent);
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .progress-current {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .import-results {
    max-height: 200px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .import-result-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
  }

  .import-result-item.ok { color: var(--color-success); }
  .import-result-item.duplikat { color: var(--color-warning); }
  .import-result-item.fehler { color: var(--color-error); }

  .result-icon { width: 1rem; text-align: center; flex-shrink: 0; }
  .result-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .result-detail { flex-shrink: 0; opacity: 0.7; }

  /* Suchergebnisse */
  .results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .results-count {
    font-size: 0.875rem;
    color: var(--color-text-muted);
    font-weight: 600;
  }

  .results-actions {
    display: flex;
    gap: 0.5rem;
  }

  .results-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .result-card {
    display: flex;
    gap: 0.75rem;
    padding: 0.75rem;
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    background: var(--glass-bg);
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
    text-align: left;
    width: 100%;
    align-items: flex-start;
  }

  .result-card:hover {
    background: var(--glass-bg-btn);
  }

  .result-card.selected {
    border-color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 8%, transparent);
  }

  .result-check {
    font-size: 1.125rem;
    color: var(--color-text-muted);
    flex-shrink: 0;
    padding-top: 0.125rem;
  }

  .result-card.selected .result-check {
    color: var(--color-accent);
  }

  .result-cover {
    width: 50px;
    height: 70px;
    object-fit: cover;
    border-radius: 4px;
    flex-shrink: 0;
    background: var(--color-bg-tertiary);
  }

  .result-cover-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-text-muted);
    font-size: 1.25rem;
  }

  .result-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .result-titel {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.3;
  }

  .result-autor {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
  }

  .result-meta {
    display: flex;
    gap: 0.375rem;
    flex-wrap: wrap;
  }

  .meta-tag {
    font-size: 0.6875rem;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    background: var(--color-bg-tertiary);
    color: var(--color-text-muted);
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
  }

  .meta-tag.format {
    background: color-mix(in srgb, var(--color-accent) 15%, transparent);
    color: var(--color-accent);
    font-weight: 600;
  }

  /* Paginierung */
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
  }

  .page-info {
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }

  .empty-state {
    text-align: center;
    padding: 2rem;
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }

  .empty-state i {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    display: block;
    opacity: 0.4;
  }
</style>
