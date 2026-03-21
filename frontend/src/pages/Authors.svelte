<script>
  import { holeAutoren, autorenFotoUrl, batchScanEvents, brecheBatchScanAb, autorenStatistik, loescheVerwaiste, resyncAutoren } from "../lib/api/authors.js";
  import { onMount, onDestroy } from "svelte";

  let autoren = $state([]);
  let gesamt = $state(0);
  let seite = $state(1);
  let seitenGesamt = $state(0);
  let laden = $state(true);
  let nachladenAktiv = $state(false);
  let alleGeladen = $state(false);
  let suche = $state("");
  let suchTimer = $state(null);
  let sortierung = $state("name");
  let richtung = $state("asc");

  // Scroll-basiertes Lazy Loading
  let scrollContainer = $state(null);

  // Batch-Scan State
  let scanAktiv = $state(false);
  let scanFortschritt = $state({ index: 0, gesamt: 0, name: "" });
  let scanErgebnisse = $state([]);
  let scanStats = $state({ gefunden: 0, nicht_gefunden: 0, fehler: 0 });
  let scanFertig = $state(false);
  let scanAutoUebernehmen = $state(true);
  let scanController = $state(null);

  // Statistik
  let statistik = $state(null);

  // Verwaiste Autoren
  let verwaistLaden = $state(false);
  let verwaistErgebnis = $state(null);

  // Resync
  let resyncLaden = $state(false);
  let resyncErgebnis = $state(null);

  function onScroll() {
    if (alleGeladen || nachladenAktiv || laden) return;
    if (!scrollContainer) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
    if (scrollTop + clientHeight >= scrollHeight - 300) {
      ladeNaechsteSeite();
    }
  }

  onMount(() => {
    ladeAutoren();
    ladeStatistik();
    // Scroll-Container ist das uebergeordnete <main>-Element
    scrollContainer = document.querySelector('main');
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', onScroll, { passive: true });
    }
  });

  onDestroy(() => {
    if (scanController) scanController.close();
    if (scrollContainer) {
      scrollContainer.removeEventListener('scroll', onScroll);
    }
  });

  async function ladeStatistik() {
    try {
      statistik = await autorenStatistik();
    } catch { /* ignore */ }
  }

  async function ladeAutoren() {
    laden = true;
    seite = 1;
    alleGeladen = false;
    try {
      const result = await holeAutoren({
        seite: 1,
        pro_seite: 36,
        suche: suche || undefined,
        sortierung,
        richtung,
      });
      autoren = result.autoren;
      gesamt = result.gesamt;
      seitenGesamt = result.seiten_gesamt;
      if (seite >= seitenGesamt) alleGeladen = true;
    } catch (e) {
      console.error("Autoren laden fehlgeschlagen:", e);
    } finally {
      laden = false;
    }
  }

  async function ladeNaechsteSeite() {
    if (nachladenAktiv || alleGeladen || laden) return;
    nachladenAktiv = true;
    seite++;
    try {
      const result = await holeAutoren({
        seite,
        pro_seite: 36,
        suche: suche || undefined,
        sortierung,
        richtung,
      });
      autoren = [...autoren, ...result.autoren];
      gesamt = result.gesamt;
      seitenGesamt = result.seiten_gesamt;
      if (seite >= seitenGesamt) alleGeladen = true;
    } catch (e) {
      console.error("Nachladen fehlgeschlagen:", e);
      seite--;
    } finally {
      nachladenAktiv = false;
    }
  }

  function onSuche(e) {
    suche = e.target.value;
    clearTimeout(suchTimer);
    suchTimer = setTimeout(() => {
      seite = 1;
      ladeAutoren();
    }, 300);
  }

  function aendereSortierung(s) {
    if (sortierung === s) {
      richtung = richtung === "asc" ? "desc" : "asc";
    } else {
      sortierung = s;
      richtung = "asc";
    }
    seite = 1;
    ladeAutoren();
  }

  function fotoFehler(e) {
    e.target.style.display = "none";
    e.target.nextElementSibling?.classList.add("sichtbar");
  }

  function starteScan() {
    scanAktiv = true;
    scanFertig = false;
    scanErgebnisse = [];
    scanStats = { gefunden: 0, nicht_gefunden: 0, fehler: 0 };
    scanFortschritt = { index: 0, gesamt: 0, name: "" };

    scanController = batchScanEvents(
      { nurOhneWikidata: true, autoUebernehmen: scanAutoUebernehmen },
      (event) => {
        switch (event.typ) {
          case "start":
            scanFortschritt = { index: 0, gesamt: event.gesamt, name: "" };
            break;
          case "suche":
            scanFortschritt = { index: event.index, gesamt: event.gesamt, name: event.name };
            break;
          case "gefunden":
            scanStats.gefunden++;
            scanErgebnisse = [...scanErgebnisse, {
              autor_id: event.autor_id,
              name: event.name,
              status: "gefunden",
              vorschlag: event.vorschlag,
              uebernommen: event.uebernommen,
            }];
            break;
          case "nicht_gefunden":
            scanStats.nicht_gefunden++;
            scanErgebnisse = [...scanErgebnisse, {
              autor_id: event.autor_id,
              name: event.name,
              status: "nicht_gefunden",
            }];
            break;
          case "fehler":
            scanStats.fehler++;
            scanErgebnisse = [...scanErgebnisse, {
              autor_id: event.autor_id,
              name: event.name,
              status: "fehler",
              fehler: event.fehler,
            }];
            break;
          case "fertig":
          case "abgebrochen":
            scanAktiv = false;
            scanFertig = true;
            ladeAutoren();
            ladeStatistik();
            break;
        }
      },
      () => {
        scanAktiv = false;
        scanFertig = true;
      }
    );
  }

  async function stoppeScan() {
    if (scanController) scanController.close();
    try { await brecheBatchScanAb(); } catch { /* ignore */ }
    scanAktiv = false;
    scanFertig = true;
    ladeAutoren();
  }

  async function resync() {
    if (resyncLaden) return;
    resyncLaden = true;
    resyncErgebnis = null;
    try {
      resyncErgebnis = await resyncAutoren();
      ladeAutoren();
      ladeStatistik();
    } catch (e) {
      resyncErgebnis = { fehler: e.message };
    } finally {
      resyncLaden = false;
    }
  }

  async function bereinigen() {
    if (verwaistLaden) return;
    verwaistLaden = true;
    verwaistErgebnis = null;
    try {
      const result = await loescheVerwaiste();
      verwaistErgebnis = result;
      if (result.gelöscht > 0) {
        ladeAutoren();
        ladeStatistik();
      }
    } catch (e) {
      verwaistErgebnis = { fehler: e.message };
    } finally {
      verwaistLaden = false;
    }
  }

  let scanProzent = $derived(
    scanFortschritt.gesamt > 0
      ? Math.round((scanFortschritt.index / scanFortschritt.gesamt) * 100)
      : 0
  );
</script>

<div class="autoren-seite">
  <div class="seiten-kopf">
    <h1 class="seiten-titel"><i class="fa-solid fa-users"></i> Autoren</h1>
    <span class="seiten-zaehler">{gesamt}</span>
  </div>

  <!-- Statistik-Leiste -->
  {#if statistik}
    <div class="stats-leiste">
      <span class="stat-item">
        <i class="fa-solid fa-users"></i> {statistik.gesamt} Autoren
      </span>
      <span class="stat-item">
        <i class="fa-brands fa-wikipedia-w"></i> {statistik.mit_wikidata} mit Wikidata
      </span>
      <span class="stat-item">
        <i class="fa-solid fa-camera"></i> {statistik.mit_foto} mit Foto
      </span>
      <span class="stat-item">
        <i class="fa-solid fa-file-lines"></i> {statistik.mit_biografie} mit Biografie
      </span>
      {#if statistik.gesamt - statistik.mit_wikidata > 0}
        <span class="stat-item offen">
          <i class="fa-solid fa-circle-question"></i> {statistik.gesamt - statistik.mit_wikidata} offen
        </span>
      {/if}
    </div>
  {/if}

  <!-- Batch-Scan Panel -->
  <div class="scan-panel">
    {#if scanAktiv}
      <div class="scan-aktiv">
        <div class="scan-kopf">
          <span class="scan-titel">
            <i class="fa-solid fa-spinner fa-spin"></i> Wikipedia-Scan
          </span>
          <span class="scan-zaehler">{scanFortschritt.index} / {scanFortschritt.gesamt}</span>
          <button class="scan-stop" onclick={stoppeScan}>
            <i class="fa-solid fa-stop"></i> Stopp
          </button>
        </div>
        <div class="scan-bar-wrap">
          <div class="scan-bar" style="width: {scanProzent}%"></div>
        </div>
        {#if scanFortschritt.name}
          <div class="scan-aktuell">
            Suche: <strong>{scanFortschritt.name}</strong>
          </div>
        {/if}
        <div class="scan-stats-zeile">
          <span class="ss gefunden"><i class="fa-solid fa-check"></i> {scanStats.gefunden}</span>
          <span class="ss nicht-gefunden"><i class="fa-solid fa-minus"></i> {scanStats.nicht_gefunden}</span>
          {#if scanStats.fehler > 0}
            <span class="ss fehler"><i class="fa-solid fa-xmark"></i> {scanStats.fehler}</span>
          {/if}
        </div>
      </div>
    {:else if scanFertig && scanErgebnisse.length > 0}
      <div class="scan-ergebnis">
        <div class="scan-kopf">
          <span class="scan-titel">
            <i class="fa-solid fa-check-circle"></i> Scan abgeschlossen
          </span>
          <button class="scan-btn-sm" onclick={() => { scanFertig = false; scanErgebnisse = []; }}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="scan-stats-zeile">
          <span class="ss gefunden"><i class="fa-solid fa-check"></i> {scanStats.gefunden} gefunden</span>
          <span class="ss nicht-gefunden"><i class="fa-solid fa-minus"></i> {scanStats.nicht_gefunden} nicht gefunden</span>
          {#if scanStats.fehler > 0}
            <span class="ss fehler"><i class="fa-solid fa-xmark"></i> {scanStats.fehler} Fehler</span>
          {/if}
        </div>
        <!-- Ergebnis-Liste (nur gefundene) -->
        {#if scanErgebnisse.filter(e => e.status === "gefunden").length > 0}
          <div class="scan-liste">
            {#each scanErgebnisse.filter(e => e.status === "gefunden") as e (e.autor_id)}
              <a href="/author/{e.autor_id}" class="scan-treffer">
                <span class="scan-treffer-name">{e.name}</span>
                <span class="scan-treffer-pfeil">-></span>
                <span class="scan-treffer-wiki">{e.vorschlag?.name || ""}</span>
                {#if e.vorschlag?.konfidenz}
                  <span class="scan-konfidenz {e.vorschlag.konfidenz}">{e.vorschlag.konfidenz}</span>
                {/if}
                {#if e.uebernommen}
                  <span class="scan-uebernommen"><i class="fa-solid fa-check"></i></span>
                {/if}
              </a>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div class="scan-start">
        <button class="scan-btn" onclick={starteScan} disabled={scanAktiv}>
          <i class="fa-brands fa-wikipedia-w"></i> Wikipedia-Scan starten
        </button>
        <label class="scan-option">
          <input type="checkbox" bind:checked={scanAutoUebernehmen} />
          Hohe Konfidenz automatisch übernehmen
        </label>
        <button class="bereinigen-btn" onclick={resync} disabled={resyncLaden} title="Autoren-Tabelle komplett aus Buchdaten neu aufbauen">
          {#if resyncLaden}
            <i class="fa-solid fa-spinner fa-spin"></i>
          {:else}
            <i class="fa-solid fa-arrows-rotate"></i>
          {/if}
          Resync
        </button>
        {#if resyncErgebnis}
          <span class="bereinigen-ergebnis">
            {#if resyncErgebnis.fehler}
              <span class="fehler-text">{resyncErgebnis.fehler}</span>
            {:else}
              {resyncErgebnis.gesamt} Autoren ({resyncErgebnis.neu_angelegt} neu)
            {/if}
          </span>
        {/if}
        <button class="bereinigen-btn" onclick={bereinigen} disabled={verwaistLaden}>
          {#if verwaistLaden}
            <i class="fa-solid fa-spinner fa-spin"></i>
          {:else}
            <i class="fa-solid fa-broom"></i>
          {/if}
          Verwaiste bereinigen
        </button>
        {#if verwaistErgebnis}
          <span class="bereinigen-ergebnis">
            {#if verwaistErgebnis.fehler}
              <span class="fehler-text">{verwaistErgebnis.fehler}</span>
            {:else if verwaistErgebnis.gelöscht > 0}
              {verwaistErgebnis.gelöscht} Autor{verwaistErgebnis.gelöscht !== 1 ? "en" : ""} entfernt
            {:else}
              Keine verwaisten Autoren
            {/if}
          </span>
        {/if}
      </div>
    {/if}
  </div>

  <div class="filter-leiste">
    <div class="such-feld">
      <i class="fa-solid fa-magnifying-glass such-icon"></i>
      <input
        type="text"
        placeholder="Autor suchen..."
        value={suche}
        oninput={onSuche}
        class="such-input"
      />
    </div>

    <div class="sort-btns">
      <button
        class="sort-btn"
        class:aktiv={sortierung === "name"}
        onclick={() => aendereSortierung("name")}
      >
        Name {sortierung === "name" ? (richtung === "asc" ? "\u2191" : "\u2193") : ""}
      </button>
      <button
        class="sort-btn"
        class:aktiv={sortierung === "buecher"}
        onclick={() => aendereSortierung("buecher")}
      >
        Bücher {sortierung === "buecher" ? (richtung === "asc" ? "\u2191" : "\u2193") : ""}
      </button>
      <button
        class="sort-btn"
        class:aktiv={sortierung === "datum"}
        onclick={() => aendereSortierung("datum")}
      >
        Datum {sortierung === "datum" ? (richtung === "asc" ? "\u2191" : "\u2193") : ""}
      </button>
    </div>
  </div>

  {#if laden}
    <p class="status-text"><i class="fa-solid fa-spinner fa-spin"></i> Autoren werden geladen...</p>
  {:else if autoren.length === 0}
    <p class="status-text">Keine Autoren gefunden</p>
  {:else}
    <div class="autoren-grid">
      {#each autoren as autor (autor.id)}
        <a href="/author/{autor.id}" class="autor-karte">
          <div class="autor-foto-wrap">
            {#if autor.photo_path}
              <img
                src={autorenFotoUrl(autor.id, "thumb")}
                alt={autor.name}
                class="autor-foto"
                onerror={fotoFehler}
                loading="lazy"
              />
            {/if}
            <div class="autor-foto-placeholder" class:sichtbar={!autor.photo_path}>
              <i class="fa-solid fa-user"></i>
            </div>
          </div>
          <div class="autor-info">
            <span class="autor-name">{autor.name}</span>
            {#if autor.birth_year || autor.death_year}
              <span class="autor-jahre">
                {autor.birth_year || "?"} - {autor.death_year || ""}
              </span>
            {/if}
            {#if autor.book_count > 0}
              <span class="autor-buecher">
                {autor.book_count} {autor.book_count === 1 ? "Buch" : "Bücher"}
              </span>
            {/if}
          </div>
        </a>
      {/each}
    </div>

    <!-- Lazy Loading Anzeige -->
    {#if nachladenAktiv}
      <div class="lade-sentinel">
        <p class="status-text"><i class="fa-solid fa-spinner fa-spin"></i> Weitere laden...</p>
      </div>
    {/if}
  {/if}
</div>

<style>
  .autoren-seite {
    width: 100%;
  }

  .seiten-kopf {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.25rem;
  }

  .seiten-titel {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .seiten-zaehler {
    font-size: 0.875rem;
    color: var(--color-text-muted);
    background-color: var(--color-bg-tertiary);
    padding: 0.125rem 0.5rem;
    border-radius: 999px;
  }

  .filter-leiste {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 1.25rem;
    flex-wrap: wrap;
  }

  .such-feld {
    position: relative;
    flex: 1;
    min-width: 200px;
  }

  .such-icon {
    position: absolute;
    left: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-text-muted);
    font-size: 0.8125rem;
  }

  .such-input {
    width: 100%;
    padding: 0.5rem 0.75rem 0.5rem 2rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
  }

  .such-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .sort-btns {
    display: flex;
    gap: 0.25rem;
  }

  .sort-btn {
    padding: 0.375rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    white-space: nowrap;
  }

  .sort-btn.aktiv {
    border-color: var(--color-accent);
    color: var(--color-accent);
    background-color: color-mix(in srgb, var(--color-accent) 10%, transparent);
  }

  .status-text {
    color: var(--color-text-muted);
    padding: 2rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* Grid */
  .autoren-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 1rem;
  }

  .autor-karte {
    display: flex;
    flex-direction: column;
    text-decoration: none;
    border-radius: 8px;
    overflow: hidden;
    transition: transform 0.15s, box-shadow 0.15s;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
  }

  .autor-karte:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    border-color: var(--color-accent);
  }

  .autor-foto-wrap {
    position: relative;
    aspect-ratio: 3 / 4;
    overflow: hidden;
    background-color: var(--color-bg-tertiary);
  }

  .autor-foto {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .autor-foto-placeholder {
    position: absolute;
    inset: 0;
    display: none;
    align-items: center;
    justify-content: center;
    font-size: 2.5rem;
    color: var(--color-text-muted);
    opacity: 0.4;
  }

  .autor-foto-placeholder.sichtbar {
    display: flex;
  }

  .autor-info {
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .autor-name {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .autor-jahre {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
  }

  .autor-buecher {
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
  }

  /* Lazy Loading Sentinel */
  .lade-sentinel {
    min-height: 1px;
    margin-top: 1rem;
    display: flex;
    justify-content: center;
  }

  /* Statistik */
  .stats-leiste {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
    padding: 0.5rem 0.75rem;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
  }

  .stat-item {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .stat-item.offen {
    color: var(--color-warning, #f59e0b);
  }

  /* Scan-Panel */
  .scan-panel {
    margin-bottom: 1rem;
  }

  .scan-start {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .scan-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 6px;
    background-color: var(--color-accent);
    color: #fff;
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.1s;
  }

  .scan-btn:hover { opacity: 0.9; }
  .scan-btn:disabled { opacity: 0.5; cursor: default; }

  .scan-option {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
    cursor: pointer;
  }

  .scan-option input {
    accent-color: var(--color-accent);
  }

  .bereinigen-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .bereinigen-btn:hover { background-color: var(--color-bg-tertiary); }
  .bereinigen-btn:disabled { opacity: 0.5; cursor: default; }

  .bereinigen-ergebnis {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .fehler-text {
    color: var(--color-error);
  }

  .scan-aktiv, .scan-ergebnis {
    padding: 0.75rem;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .scan-kopf {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .scan-titel {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .scan-zaehler {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }

  .scan-stop {
    margin-left: auto;
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-error);
    border-radius: 4px;
    background: none;
    color: var(--color-error);
    font-size: 0.75rem;
    cursor: pointer;
  }

  .scan-stop:hover { background-color: var(--color-error); color: #fff; }

  .scan-btn-sm {
    margin-left: auto;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.625rem;
    cursor: pointer;
  }

  .scan-bar-wrap {
    height: 4px;
    background-color: var(--color-bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
  }

  .scan-bar {
    height: 100%;
    background-color: var(--color-accent);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .scan-aktuell {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .scan-aktuell strong {
    color: var(--color-text-primary);
  }

  .scan-stats-zeile {
    display: flex;
    gap: 0.75rem;
  }

  .ss {
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .ss.gefunden { color: var(--color-success, #22c55e); }
  .ss.nicht-gefunden { color: var(--color-text-muted); }
  .ss.fehler { color: var(--color-error); }

  /* Ergebnis-Liste */
  .scan-liste {
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 300px;
    overflow-y: auto;
    margin-top: 0.25rem;
  }

  .scan-treffer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    text-decoration: none;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    transition: background-color 0.1s;
  }

  .scan-treffer:hover {
    background-color: var(--color-bg-tertiary);
  }

  .scan-treffer-name {
    color: var(--color-text-primary);
    font-weight: 500;
  }

  .scan-treffer-pfeil {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: 0.625rem;
  }

  .scan-treffer-wiki {
    color: var(--color-accent);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .scan-konfidenz {
    font-size: 0.5625rem;
    font-weight: 600;
    padding: 0.0625rem 0.375rem;
    border-radius: 999px;
    text-transform: uppercase;
  }

  .scan-konfidenz.hoch {
    background-color: color-mix(in srgb, var(--color-success, #22c55e) 15%, transparent);
    color: var(--color-success, #22c55e);
  }

  .scan-konfidenz.mittel {
    background-color: color-mix(in srgb, var(--color-warning, #f59e0b) 15%, transparent);
    color: var(--color-warning, #f59e0b);
  }

  .scan-konfidenz.niedrig {
    background-color: color-mix(in srgb, var(--color-text-muted) 15%, transparent);
    color: var(--color-text-muted);
  }

  .scan-uebernommen {
    color: var(--color-success, #22c55e);
    font-size: 0.6875rem;
  }
</style>
