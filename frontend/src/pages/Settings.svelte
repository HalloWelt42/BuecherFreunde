<script>
  import { getToken, setToken } from "../lib/api/client.js";
  import { get } from "../lib/api/client.js";
  import { indexNeuAufbauen } from "../lib/api/search.js";
  import ServiceStatus from "../lib/components/settings/ServiceStatus.svelte";
  import BackupPanel from "../lib/components/settings/BackupPanel.svelte";
  import CategoryManager from "../lib/components/settings/CategoryManager.svelte";
  import SammlungManager from "../lib/components/settings/SammlungManager.svelte";
  import AiSettings from "../lib/components/settings/AiSettings.svelte";
  import LegalInfo from "../lib/components/settings/LegalInfo.svelte";
  import BackgroundManager from "../lib/components/settings/BackgroundManager.svelte";

  import { route } from "../lib/router.svelte.js";
  import { onMount } from "svelte";

  let activeTab = $derived.by(() => {
    if (route.path.includes("/settings/categories")) return "categories";
    if (route.path.includes("/settings/sammlungen")) return "sammlungen";
    if (route.path.includes("/settings/ai")) return "ai";
    if (route.path.includes("/settings/system")) return "system";
    if (route.path.includes("/settings/legal")) return "legal";
    return "general";
  });

  let token = $state(getToken());
  let reindexMsg = $state("");
  let paths = $state({ datenbank: "", speicher: "", import: "", extern: "" });
  let stats = $state({ buecher_gesamt: 0 });

  function saveToken() {
    setToken(token);
  }

  async function reindex() {
    reindexMsg = "Index wird neu aufgebaut...";
    try {
      const result = await indexNeuAufbauen();
      reindexMsg = result.message || "Index neu aufgebaut";
    } catch (e) {
      reindexMsg = `Fehler: ${e.message}`;
    }
  }

  onMount(async () => {
    try {
      paths = await get("/api/config/paths");
    } catch { /* still */ }
    try {
      stats = await get("/api/config/stats");
    } catch { /* still */ }
  });
</script>

<div class="settings-page">
  <div class="page-header">
    <h1>
      <i class="fa-solid fa-gear"></i> Einstellungen
    </h1>
    <nav class="settings-tabs">
      <a href="/settings" class="tab" class:active={activeTab === "general"}>
        <i class="fa-solid fa-sliders"></i> Allgemein
      </a>
      <a href="/settings/categories" class="tab" class:active={activeTab === "categories"}>
        <i class="fa-solid fa-folder"></i> Kategorien
      </a>
      <a href="/settings/sammlungen" class="tab" class:active={activeTab === "sammlungen"}>
        <i class="fa-solid fa-layer-group"></i> Sammlungen
      </a>
      <a href="/settings/ai" class="tab" class:active={activeTab === "ai"}>
        <i class="fa-solid fa-robot"></i> KI
      </a>
      <a href="/settings/system" class="tab" class:active={activeTab === "system"}>
        <i class="fa-solid fa-hard-drive"></i> System
      </a>
      <a href="/settings/legal" class="tab" class:active={activeTab === "legal"}>
        <i class="fa-solid fa-scale-balanced"></i> Rechtliches
      </a>
    </nav>
  </div>

  {#if activeTab === "categories"}
    <CategoryManager />
  {:else if activeTab === "sammlungen"}
    <SammlungManager />
  {:else if activeTab === "ai"}
    <AiSettings />
  {:else if activeTab === "legal"}
    <div class="settings-single">
      <section class="settings-section">
        <h2><i class="fa-solid fa-scale-balanced"></i> Lizenz, Datenschutz und Drittanbieter</h2>
        <p class="section-hint">Rechtliche Informationen zu BücherFreunde, verwendeten Bibliotheken und Datenschutz.</p>
        <LegalInfo />
      </section>
    </div>
  {:else if activeTab === "system"}
    <div class="settings-single">
      <section class="settings-section">
        <h2><i class="fa-solid fa-folder-open"></i> Verzeichnisse</h2>
        <p class="section-hint">Diese Pfade werden beim Start aus der Konfiguration geladen. Hier wird nichts geändert -- die Übersicht zeigt nur, wo deine Daten liegen.</p>
        <div class="path-list">
          <div class="path-row">
            <span class="path-label">Datenbank</span>
            <code class="path-value">{paths.datenbank || "--"}</code>
            <span class="path-hint">SQLite-Datenbankdatei mit allen Metadaten, Einstellungen und dem Suchindex.</span>
          </div>
          <div class="path-row">
            <span class="path-label">Bücherspeicher</span>
            <code class="path-value">{paths.speicher || "--"}</code>
            <span class="path-hint">Hash-basierter Speicher für Originaldateien, Cover und Volltexte. Per rsync sicherbar.</span>
          </div>
          <div class="path-row">
            <span class="path-label">Import-Verzeichnis</span>
            <code class="path-value">{paths.import || "--"}</code>
            <span class="path-hint">Neue Dateien hier ablegen oder hochladen. Wird beim Import-Scan durchsucht.</span>
          </div>
          {#if paths.extern}
            <div class="path-row">
              <span class="path-label">Externes Verzeichnis</span>
              <code class="path-value">{paths.extern}</code>
              <span class="path-hint">Externer Mount (USB, Netzlaufwerk). Dient als zusätzliche Import-Quelle und zur Duplikaterkennung.</span>
            </div>
          {/if}
        </div>
        <div class="stats-row">
          <span class="stat"><strong>{stats.buecher_gesamt}</strong> Bücher</span>
        </div>
      </section>

      <section class="settings-section">
        <h2><i class="fa-solid fa-database"></i> Datenbank</h2>
        <p class="section-hint">Der Suchindex (FTS) macht die Volltextsuche möglich. Normalerweise aktualisiert er sich automatisch. Nur bei Problemen mit der Suche manuell neu aufbauen.</p>
        <div class="setting-row">
          <button class="btn-secondary" onclick={reindex}>
            <i class="fa-solid fa-rotate"></i> FTS-Index neu aufbauen
          </button>
          {#if reindexMsg}
            <span class="msg">{reindexMsg}</span>
          {/if}
        </div>
      </section>

      <section class="settings-section">
        <h2><i class="fa-solid fa-box-archive"></i> Backup</h2>
        <p class="section-hint">Erstellt ein Backup deiner Datenbank, Einstellungen und Metadaten als ZIP-Datei. Die Buchdateien selbst sind nicht enthalten -- die sicherst du am besten per rsync vom Bücherspeicher-Verzeichnis.</p>
        <BackupPanel />
      </section>
    </div>
  {:else}
    <div class="settings-single">
      <section class="settings-section">
        <h2><i class="fa-solid fa-key"></i> API-Token</h2>
        <p class="section-hint">Das Token verbindet dein Frontend mit dem Backend. Es wird beim ersten Start automatisch generiert. Nur ändern, wenn du es bewusst neu setzen möchtest.</p>
        <div class="token-row">
          <input
            type="text"
            class="form-input mono"
            bind:value={token}
            placeholder="API-Token eingeben"
          />
          <button class="btn-primary" onclick={saveToken}>
            <i class="fa-solid fa-check"></i> Speichern
          </button>
        </div>
      </section>

      <section class="settings-section">
        <h2><i class="fa-solid fa-image"></i> Hintergrundbilder</h2>
        <p class="section-hint">Lade Hintergrundbilder hoch, die auf der Buch-Detailseite als Hintergrund angezeigt werden. Zwischen mehreren Bildern kannst du im Header mit den Pfeilen wechseln. Die Auswahl wird dauerhaft gespeichert.</p>
        <BackgroundManager />
      </section>

      <section class="settings-section">
        <h2><i class="fa-solid fa-plug"></i> Externe Dienste</h2>
        <p class="section-hint">Hier siehst du, welche externen Dienste verbunden sind. Grün bedeutet erreichbar, rot bedeutet nicht verfügbar -- betroffene Funktionen werden dann automatisch deaktiviert. Nichts davon ist zwingend nötig.</p>
        <ServiceStatus />
      </section>
    </div>
  {/if}
</div>

<style>
  .settings-page {
    max-width: 1200px;
  }

  .page-header {
    margin-bottom: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    position: sticky;
    top: -1.5rem;
    z-index: 10;
    background-color: var(--color-bg-primary);
    margin: -1.5rem -1.5rem 1.5rem;
    padding: 1.5rem 1.5rem 0;
  }

  .page-header h1 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .page-header h1 i {
    color: var(--color-accent);
  }

  .settings-tabs {
    display: flex;
    gap: 0.25rem;
    border-bottom: 1px solid var(--color-border);
  }

  .tab {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    border-bottom: 2px solid transparent;
    color: var(--color-text-secondary);
    text-decoration: none;
    font-size: 0.8125rem;
    font-weight: 500;
    transition: all 0.12s;
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--color-text-primary);
  }

  .tab.active {
    color: var(--color-accent);
    border-bottom-color: var(--color-accent);
  }

  .settings-single {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .settings-section {
    padding: 1rem;
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
  }

  .settings-section h2 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.75rem;
  }

  .settings-section h2 i {
    font-size: 0.8125rem;
    color: var(--color-accent);
    width: 1rem;
    text-align: center;
  }

  .section-hint {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: -0.25rem 0 0.75rem 0;
  }

  .setting-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.25rem 0;
  }

  /* Token */
  .token-row {
    display: flex;
    gap: 0.5rem;
  }

  .form-input {
    flex: 1;
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--glass-placeholder);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: var(--font-sans);
  }

  .form-input.mono {
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .form-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  /* Buttons */
  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border: none;
    border-radius: 6px;
    background-color: var(--color-accent);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: opacity 0.1s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.1s;
  }

  .btn-secondary:hover {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
    border-color: var(--color-accent);
  }

  /* Pfade */
  .path-list {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .path-row {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    margin-bottom: 0.25rem;
  }

  .path-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .path-value {
    font-size: 0.8125rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background-color: var(--color-bg-primary);
    padding: 0.25rem 0.375rem;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    word-break: break-all;
  }

  .path-hint {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    line-height: 1.4;
  }

  .stats-row {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
  }

  .stat {
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }

  .stat strong {
    color: var(--color-text-primary);
    font-weight: 600;
  }

  .msg {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
</style>
